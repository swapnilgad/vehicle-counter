import cv2  # OpenCV for video processing
from ultralytics import YOLO  # YOLOv8 object detection model
import numpy as np
import datetime  # For timestamps
import csv  # To save vehicle logs in a CSV
import os  # To check/create folders
import signal  # To handle clean shutdown
import sys  # For exiting safely
import sqlite3  # To store vehicle count in a database

# === Configuration Settings ===
webcam_index = 0  # Index of webcam (0 is usually default internal webcam)
model_path = "yolov8n.pt"  # Path to the YOLOv8 model
count_line_position = 270  # Y-axis line for vehicle counting
offset = 20  # Range of tolerance for the counting line

# === Load YOLOv8 Model ===
model = YOLO("runs/detect/train3/weights/best.pt")

# === Initialize Webcam Feed ===
cap = cv2.VideoCapture(webcam_index)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

# === Variables to Keep Count of Vehicles ===
count_cars = count_bikes = count_trucks = 0
counted_ids = set()  # To avoid counting the same vehicle multiple times

# === Create 'logs' Directory If Not Present ===
if not os.path.exists("logs"):
    os.makedirs("logs")

# === Prepare CSV File for Logging ===
filename = datetime.datetime.now().strftime("logs/vehicle_log_%Y%m%d.csv")
csv_file = open(filename, mode='a', newline='')
csv_writer = csv.writer(csv_file)

# Add headers if it's a new file
if os.path.getsize(filename) == 0:
    csv_writer.writerow(["Timestamp", "Vehicle Type", "Vehicle ID"])

# === Connect to SQLite Database ===
db_conn = sqlite3.connect("vehicle_data.db", check_same_thread=False)
db_cursor = db_conn.cursor()

# Create vehicles table if it doesn't already exist
db_cursor.execute("""
CREATE TABLE IF NOT EXISTS vehicles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT,
    vehicle_type TEXT,
    vehicle_id INTEGER
)
""")
db_conn.commit()

# === Clean Exit When User Presses Ctrl+C or Program Stops ===
def cleanup(*args):
    print("\n🔻 Exiting... Saving data.")
    csv_file.close()
    cap.release()  # Release webcam
    db_conn.close()  # Close DB connection
    cv2.destroyAllWindows()
    sys.exit(0)

# Attach the cleanup function to shutdown signals
signal.signal(signal.SIGINT, cleanup)
signal.signal(signal.SIGTERM, cleanup)

# === Start Processing Each Frame From Webcam ===
frame_count = 0
while True:
    ret, frame = cap.read()
    if not ret:
        print("❌ Failed to grab frame. Retrying...")
        continue

    # Skip every alternate frame to reduce lag
    frame_count += 1
    if frame_count % 2 != 0:
        continue

    # Detect and track objects using YOLOv8 + ByteTrack
    results = model.track(frame, persist=True, conf=0.5, tracker="bytetrack.yaml")

    # If detection results are found
    if results[0].boxes.id is not None:
        boxes = results[0].boxes
        ids = boxes.id.cpu().numpy()  # Unique ID per object
        classes = boxes.cls.cpu().numpy()  # Class index (car, truck, etc.)
        coords = boxes.xyxy.cpu().numpy()  # Bounding box coordinates
        confs = boxes.conf.cpu().numpy()  # Confidence scores

        # Loop through each detection
        for box_id, cls, coord, conf in zip(ids, classes, coords, confs):
            x1, y1, x2, y2 = coord
            center_y = int((y1 + y2) / 2)  # Center Y of bounding box
            label = model.names[int(cls)]  # Get label like 'car' from class index

            # Only count cars, bikes, or trucks with good confidence
            if label in ["car", "motorcycle", "truck"] and conf > 0.5:
                # Draw bounding box and label on the frame
                cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
                cv2.putText(frame, f"{label}-{int(box_id)}", (int(x1), int(y1) - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)

                # Check if the object has crossed the count line and hasn't been counted yet
                if (count_line_position - offset < center_y < count_line_position + offset and
                        box_id not in counted_ids):
                    counted_ids.add(box_id)  # Mark this ID as counted

                    # Save timestamp and log data
                    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    csv_writer.writerow([timestamp, label, int(box_id)])

                    # Save to database
                    db_cursor.execute(
                        "INSERT INTO vehicles (timestamp, vehicle_type, vehicle_id) VALUES (?, ?, ?)",
                        (timestamp, label, int(box_id))
                    )
                    db_conn.commit()

                    print(f"✔ Counted {label}-{int(box_id)} at {timestamp}")

                    # Increase vehicle-type specific count
                    if label == "car":
                        count_cars += 1
                    elif label == "motorcycle":
                        count_bikes += 1
                    elif label == "truck":
                        count_trucks += 1

    # === Draw a Horizontal Red Line to Represent the Counting Line ===
    cv2.line(frame, (0, count_line_position), (frame.shape[1], count_line_position), (0, 0, 255), 2)

    # === Display Current Counts on Screen ===
    cv2.putText(frame, f"Cars: {count_cars} | Bikes: {count_bikes} | Trucks: {count_trucks}",
                (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)

    # === Show the Frame in a Window ===
    cv2.imshow("Vehicle Detection & Counting (Webcam)", frame)

    # If ESC key is pressed, stop the program
    if cv2.waitKey(1) == 27:
        cleanup()