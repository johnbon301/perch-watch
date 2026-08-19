import time
import cv2
from ultralytics import YOLO
import turretMovement.py

# fine-tunned models goes here
""" Add explaniation to README to obtain model for script """

speciesOnlyModel = YOLO('./models/speciesOnly/birdDetectionUmatilla_ncnn_model')
birdOnlyModel = YOLO('./models/birdOnly/bird_detection(best_weight)v2_ncnn_model')
model = YOLO('yolo11n.pt')

# put species in a list which is captured on the species model metadata
DETER_CLASS = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]


# fps stuff
pTime = 0
cTime = 0

# setting up camera
cap = cv2.VideoCapture(0)  # creates a capture object that opens up the default camera (0)

if not cap.isOpened():
    raise RuntimeError("Camera failed to open")

# sets the height and width of the window size
cap.set(3, 640) 
cap.set(4, 480)


""" Two models are needed for this script to work. The stage 1 part will only detect for bird and nothing else.
    Need to make sure endangered species are on this part too. The second stage will crop the bounded box for the 
    second model to detect which species it is looking at. This will log the certain species
"""
while True:  # infinite loop
    success, frame = cap.read()  # returns to values that successfully captures the frame (always have)
    if not success:
        break

    # load and detect
    results = model(frame, conf=0.5, classes=[0], stream=True)
    results = birdOnlyModel(frame, conf=0.5, classes=[0] ,stream=True)

    """
    for every result from model, extract every box and its point, calculate mid point, convert those mid points to an angle where 
    the servos can move. add edges cases for when the coorindates push the turrent beyond the angles. Make sure that every second
    or so, there is a sleep timer to prevent continous firing. Control preassure to ensure it does not harm bird either. Probably 
    a sleep timer where after the first second. Make sure if a bird is endanger to avoid completely
    """
    # extracts the points and converts them to the middle of the box
    for box in results.boxes[0]:
        x1, y1, x2, y2 = box.xyxy
        xm, ym = (x1 + x2) / 2, (y1 + y2) / 2

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