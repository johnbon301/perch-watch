import time
import os
import csv
import cv2
from datetime import datetime
from ultralytics import YOLO
import turretMovement

LOG_DIR = "./sightings"
IMAGE_DIR = os.path.join(LOG_DIR, "images")
CSV_PATH = os.path.join(LOG_DIR, "sightings.csv")

def calculatePanTilt(xm, ym, FRAME_WIDTH, FRAME_HEIGHT, initalPanAngle, initalTiltAngle, HFOV, VFOV):
    # pan
    offsetRatioX = (xm - FRAME_WIDTH / 2) / (FRAME_WIDTH / 2) # based on a number between -1 and 1
    panOffset = offsetRatioX * (HFOV / 2)
    targetPan = max(0, min(180, initalPanAngle + panOffset))
    # tilt
    offsetRatioY = (ym - FRAME_HEIGHT / 2) / (FRAME_HEIGHT / 2)
    tiltOffset = offsetRatioY * (VFOV / 2)
    targetTilt = max(80, min(180, initalTiltAngle + tiltOffset))  # confirm real tilt limits

    return targetPan, targetTilt

def isActiveHour(currentHour, startHour, endHour):
    # handles windows that wrap past midnight (e.g. active 5am-10pm, inactive 10pm-5am)
    if startHour <= endHour:
        return startHour <= currentHour < endHour
    return currentHour >= startHour or currentHour < endHour

def birdCheck(results):
    # extracts the points and converts them to the middle of the box
    if len(results[0].boxes) > 0:
        # need to convert to list since YOLO returns PyTorch Tensors
        xyxy_list = results[0].boxes.xyxy.tolist()
        biggestBox = max(xyxy_list, key=lambda box: (box[2] - box[0]) * (box[3] - box[1]))
        x1, y1, x2, y2 = biggestBox
        xm, ym = (x1 + x2) / 2, (y1 + y2) / 2

        return x1, y1, x2, y2, xm, ym

def speciesCheck(frame, speciesOnlyModel, x1, y1, x2, y2):
    # crop the detected bird out of the frame and run it through the species model
    speciesName = None
    speciesConf = None
    croppedBird = frame[int(y1):int(y2), int(x1):int(x2)]

    if croppedBird.size > 0: # makes sure there is a frame to send to the model
        speciesResults = speciesOnlyModel(croppedBird, conf=0.45)
        speciesBoxes = speciesResults[0].boxes

        if len(speciesBoxes) > 0:
            topIdx = int(speciesBoxes.conf.argmax()) # takes highest confidence rate of frame for species
            speciesClassId = int(speciesBoxes.cls[topIdx])
            speciesName = speciesOnlyModel.names[speciesClassId]
            speciesConf = float(speciesBoxes.conf[topIdx])

    return speciesName, speciesConf, croppedBird

def speciesLogging(speciesName, speciesConf, croppedBird, nextSightingId):
    # holds a csv file that contains species name, time and date, each photo corresponding with an ID #
    # to find in csv file (ex 1.png, 2.png, 3.png, etc.). had claude help me with this feature
    os.makedirs(IMAGE_DIR, exist_ok=True)

    imagePath = os.path.join(IMAGE_DIR, f"{nextSightingId}.png")
    cv2.imwrite(imagePath, croppedBird)

    fileExists = os.path.isfile(CSV_PATH)
    with open(CSV_PATH, mode="a", newline="") as csvFile:
        writer = csv.writer(csvFile)

        if not fileExists:
            writer.writerow(["id", "species", "confidence", "timestamp"])
        writer.writerow([nextSightingId, speciesName, f"{speciesConf:.2f}", datetime.now().strftime("%Y-%m-%d %H:%M:%S")])

    return nextSightingId + 1

def turretAdjustment(targetPan, targetTilt, SMOOTHINGFACTOR, DEADBAND_DEGREES, turret,
                      prevPanAngle, prevTiltAngle, currentPanAngle, currentTiltAngle):
    # smooth the target to reduce jitter from small frame-to-frame detection noise
    targetPan = prevPanAngle + SMOOTHINGFACTOR * (targetPan - prevPanAngle)
    targetTilt = prevTiltAngle + SMOOTHINGFACTOR * (targetTilt - prevTiltAngle)
    prevPanAngle, prevTiltAngle = targetPan, targetTilt

    # skip corrections too small to matter, avoids chasing the servo's own mechanical slop, had claude help with this one
    if abs(targetPan - currentPanAngle) > DEADBAND_DEGREES or abs(targetTilt - currentTiltAngle) > DEADBAND_DEGREES:
        currentPanAngle, currentTiltAngle = turret.moveTurret(targetPan, targetTilt)

    return prevPanAngle, prevTiltAngle, currentPanAngle, currentTiltAngle

def main():
    PROTECTED_SPECIES = {"Haliaeetus-Leucocephalus", "Buteo-Jamaicensis"}  # bald eagle, red-tailed hawk

    # FOV for the camera in a 640x480 resolution. Calculated by taking distance, width and height
    # 2 * math.degrees(math.atan(W or H / (2 * D)))
    HFOV = 41.4
    VFOV = 31.0
    SMOOTHING_FACTOR = 0.9  # closer to 1 = faster/more jittery and closer to 0 = smoother/laggier
    DEADBAND_DEGREES = 1.5

    ACTIVE_START_HOUR = 5   # 5am
    ACTIVE_END_HOUR = 22    # 10pm, so inactive window is 10pm-5am

    """ Add explaniation to README to obtain model for script """
    # fine-tunned models goes here
    speciesOnlyModel = YOLO('./models/speciesOnly/birdDetectionUmatilla_ncnn_model')
    birdOnlyModel = YOLO('./models/birdOnly/bird_detection(best_weight)v2_ncnn_model')
    model = YOLO('./yolo11n_ncnn_model')

    # setting up camera
    cap = cv2.VideoCapture(0)  # creates a capture object that opens up the default camera (0)
    
    if not cap.isOpened():
        raise RuntimeError("Camera failed to open")

    # sets the height and width
    cap.set(3, 640) 
    cap.set(4, 480)
    FRAME_WIDTH = cap.get(3)
    FRAME_HEIGHT = cap.get(4)

    turret = turretMovement.Turret(panAngle=90, tiltAngle=140) # turret object

    initalPanAngle, initalTiltAngle = turret.moveTurret(90, 140)
    # for angle smoothness
    prevPanAngle, prevTiltAngle = initalPanAngle, initalTiltAngle
    currentPanAngle, currentTiltAngle = initalPanAngle, initalTiltAngle

    # timing stuff
    lastShotTime = 0
    SHOOT_COOLDOWN = 5.0
    lastLogTime = 0
    LOG_COOLDOWN = 300.0  # keeps the csv from filling up with one sighting repeated every frame

    # figure out where the sighting id count should resume from, so restarts don't overwrite old photos
    nextSightingId = 1
    if os.path.isfile(CSV_PATH):
        with open(CSV_PATH, mode="r", newline="") as csvFile:
            rowCount = sum(1 for _ in csv.reader(csvFile)) - 1  # minus header row
            nextSightingId = max(1, rowCount + 1)

    """ Two models are needed for this script to work. The stage 1 part will only detect for bird and nothing else.
        Need to make sure endangered species are on this part too. The second stage will crop the bounded box for the 
        second model to detect which species it is looking at. This will log the certain species
    """
    while True:  # infinite loop
        success, frame = cap.read()  # returns to values that successfully captures the frame (always have)
        if not success:
            raise RuntimeError("Frame read did not work")
        

        if isActiveHour(datetime.now().hour, ACTIVE_START_HOUR, ACTIVE_END_HOUR):
            # where detection starts
            # results = model(frame, conf=0.5, classes=[0]) # using yolo nano for temp. and aiming logic
            results = birdOnlyModel(frame, conf=0.6, classes=[0])

            """
            for every result from model, extract every box and its point, calculate mid point, convert those mid points to an angle where
            the servos can move. add edges cases for when the coorindates push the turrent beyond the angles. Make sure that every second
            or so, there is a sleep timer to prevent continous firing. Control preassure to ensure it does not harm bird either. Probably
            a sleep timer where after the first second. Make sure if a bird is endanger to avoid completely
            """
            detection = birdCheck(results)

            if detection is not None: # make sure there is a bird to prevent unnessarcy detection
                x1, y1, x2, y2, xm, ym = detection
                print("Bird Seen")

                speciesName, speciesConf, croppedBird = speciesCheck(frame, speciesOnlyModel, x1, y1, x2, y2)

                if speciesName is not None and time.time() - lastLogTime >= LOG_COOLDOWN: # prevent random bird data in csv
                    nextSightingId = speciesLogging(speciesName, speciesConf, croppedBird, nextSightingId)
                    lastLogTime = time.time()

                targetPan, targetTilt = calculatePanTilt(xm, ym, FRAME_WIDTH, FRAME_HEIGHT, initalPanAngle, initalTiltAngle, HFOV, VFOV)
                # turret movement
                prevPanAngle, prevTiltAngle, currentPanAngle, currentTiltAngle = turretAdjustment(
                    targetPan, targetTilt, SMOOTHING_FACTOR, DEADBAND_DEGREES, turret,
                    prevPanAngle, prevTiltAngle, currentPanAngle, currentTiltAngle)

                time.sleep(0.1) # gives time for servos to move

                if speciesName in PROTECTED_SPECIES:
                    print(f"protected species detected: ({speciesName})")

                elif time.time() - lastShotTime >= SHOOT_COOLDOWN:
                    turret.shoot()
                    print("BAMMM, TARGET HIT")
                    lastShotTime = time.time()
        else:
            time.sleep(1200)  # inactive hours, avoid busy-looping camera reads all night (20 min)

    # clean up properly outside the loop
    cap.release()

if __name__ == "__main__":
    main()
