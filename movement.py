import time
import cv2
from ultralytics import YOLO
import turretMovement


def calculatePanTilt(xm, ym, frameWidth, frameHeight, initalPanAngle, initalTiltAngle, hfov, vfov):
    # pan
    offsetRatioX = (xm - frameWidth / 2) / (frameWidth / 2) # based on a number between -1 and 1
    panOffset = offsetRatioX * (hfov / 2)
    targetPan = max(0, min(180, initalPanAngle + panOffset))

    # tilt
    offsetRatioY = (ym - frameHeight / 2) / (frameHeight / 2)
    tiltOffset = offsetRatioY * (vfov / 2)
    targetTilt = max(80, min(180, initalTiltAngle + tiltOffset))  # confirm real tilt limits

    return targetPan, targetTilt

def main():
    # GLOBAL VARIABLES
    SPECIES_CLASS = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10] # the birds that are being logged
    # FOV for the camera in a 640x480 resolution. Calculated by taking distance, width and height
    # 2 * math.degrees(math.atan(W or H / (2 * D)))
    hfov = 41.4
    vfov = 31.0

    """ Add explaniation to README to obtain model for script """
    # fine-tunned models goes here
    speciesOnlyModel = YOLO('./models/speciesOnly/birdDetectionUmatilla_ncnn_model')
    birdOnlyModel = YOLO('./models/birdOnly/bird_detection(best_weight)v2_ncnn_model')
    model = YOLO('yolo11n.pt')

    # setting up camera
    cap = cv2.VideoCapture(0)  # creates a capture object that opens up the default camera (0)

    if not cap.isOpened():
        raise RuntimeError("Camera failed to open")

    # sets the height and width
    cap.set(3, 640) 
    cap.set(4, 480)
    frameWidth = cap.get(3)
    frameHeight = cap.get(4)
    turret = turretMovement.Turret(panAngle=90, tiltAngle=90)
    initalPanAngle, initalTiltAngle = turret.moveTurret(90, 90) # NEED TO FIND TRUE HOME POSITION
    # fps stuff
    pTime = 0
    cTime = 0

    """ Two models are needed for this script to work. The stage 1 part will only detect for bird and nothing else.
        Need to make sure endangered species are on this part too. The second stage will crop the bounded box for the 
        second model to detect which species it is looking at. This will log the certain species
    """
    while True:  # infinite loop
        success, frame = cap.read()  # returns to values that successfully captures the frame (always have)
        if not success:
            raise RuntimeError("Frame read did not work")
        

        # load and detect
        # results = model(frame, conf=0.5, classes=[0]) # using yolo nano for temp. and aiming logic
        results = birdOnlyModel(frame, conf=0.6, classes=[0])

        """
        for every result from model, extract every box and its point, calculate mid point, convert those mid points to an angle where 
        the servos can move. add edges cases for when the coorindates push the turrent beyond the angles. Make sure that every second
        or so, there is a sleep timer to prevent continous firing. Control preassure to ensure it does not harm bird either. Probably 
        a sleep timer where after the first second. Make sure if a bird is endanger to avoid completely
        """

        # extracts the points and converts them to the middle of the box
        if len(results[0].boxes) > 0:
            # need to convert to list since YOLO returns PyTorch Tensors
            xyxy_list = results[0].boxes.xyxy.tolist()
            biggestBox = max(xyxy_list, key=lambda box: (box[2] - box[0]) * (box[3] - box[1]))
            x1, y1, x2, y2 = biggestBox
            xm, ym = (x1 + x2) / 2, (y1 + y2) / 2
            targetPan, targetTilt = calculatePanTilt(xm, ym, frameWidth, frameHeight, 
                                                            initalPanAngle, initalTiltAngle, hfov, vfov)
            currentPanAngle, currentTiltAngle = turret.moveTurret(targetPan, targetTilt)
            time.sleep(0.1)
            print(currentPanAngle)
            print(currentTiltAngle)

        # labels the frame taken from live feed
        annotatedFrame = results[0].plot()

        # sets the fps
        cTime = time.time()
        fps = 1 / (cTime - pTime)
        pTime = cTime

        cv2.putText(annotatedFrame, f' fps: {str(int(fps))}', (10, 50), cv2.FONT_HERSHEY_PLAIN, 2,
                (255, 0, 255), 2) # adds and edits the window for "Image"
        
        cv2.imshow("Result", annotatedFrame)
        # wait 1ms for the next frame, or quit if 'q' is pressed
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    # clean up properly outside the loop
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
