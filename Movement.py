import time
import cv2
from ultralytics import YOLO

# my fine-tunned model goes here
model = YOLO('./models/bird_detection(best_weight).pt')

# fps stuff
pTime = 0
cTime = 0

# setting up camera
cap = cv2.VideoCapture(0)  # creates a capture object that opens up the default camera (0)
cap.set(3, 640) # sets the height and width of the window size
cap.set(4, 480)

while True:  # infinite loop
    success, frame = cap.read()  # returns to values that successfully captures the frame (always have)
    if not success:
        break

    # load and detect
    results = model(frame, conf=0.5, verbose=False)
    # labels the frame taken from live feed
    annotatedFrame = results[0].plot()

    # sets the fps
    cTime = time.time()
    fps = 1 / (cTime - pTime)
    pTime = cTime

    cv2.putText(annotatedFrame, f' fps: {str(int(fps))}', (10, 50), cv2.FONT_HERSHEY_PLAIN, 2,
            (255, 0, 255), 2) # adds and edits the window for "Image"
    
    cv2.imshow("Result", annotatedFrame)
    # Wait 1ms for the next frame, or quit if 'q' is pressed
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# Clean up properly outside the loop
cap.release()
cv2.destroyAllWindows()

