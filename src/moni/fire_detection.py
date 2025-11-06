import cv2
import numpy as np

class FireDetector:
    def __init__(self):
        pass

    def detect_fire(self, frame):
        # Convert to HSV color space
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        # Define range for fire colors (orange/red)
        lower_fire = np.array([0, 50, 50])
        upper_fire = np.array([35, 255, 255])

        # Create mask for fire colors
        mask = cv2.inRange(hsv, lower_fire, upper_fire)

        # Find contours
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        fire_detected = False
        for contour in contours:
            if cv2.contourArea(contour) > 100:  # Minimum area threshold
                fire_detected = True
                # Draw bounding box
                x, y, w, h = cv2.boundingRect(contour)
                cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 0, 255), 2)

        return fire_detected, frame

    def process_video(self, video_path):
        cap = cv2.VideoCapture(video_path)
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            fire_detected, processed_frame = self.detect_fire(frame)
            if fire_detected:
                print("Fire detected!")

            cv2.imshow('Fire Detection', processed_frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        cap.release()
        cv2.destroyAllWindows()
