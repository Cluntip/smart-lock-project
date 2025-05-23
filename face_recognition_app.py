# face_recognition_app.py
import streamlit as st
import cv2
import numpy as np
import os
import sqlite3
import datetime
from PIL import Image
import time
import paho.mqtt.client as mqtt
import json

st.set_page_config(layout="wide")

if 'marked_students' not in st.session_state:
    st.session_state.marked_students = set()
if 'recently_marked' not in st.session_state:
    st.session_state.recently_marked = {}
if 'camera_running' not in st.session_state:
    st.session_state.camera_running = False
if 'last_access' not in st.session_state:
    st.session_state.last_access = None

class MQTTClient:
    def __init__(self):
        self.client = mqtt.Client("WebApp")
        self.client.connect("localhost", 1883)
        self.client.subscribe("smartlock/events")
        self.client.on_message = self.on_message
        
    def on_message(self, client, userdata, msg):
        try:
            st.session_state.last_access = json.loads(msg.payload)
        except Exception as e:
            st.error(f"Error processing MQTT message: {str(e)}")

mqtt_client = MQTTClient()
mqtt_client.client.loop_start()

@st.cache_resource
def load_recognizer():
    recognizer = cv2.face.LBPHFaceRecognizer_create()
    label_map = {}
    if os.path.exists("data/trained_model.yml"):
        recognizer.read("data/trained_model.yml")
    if os.path.exists("data/label_mapping.txt"):
        with open("data/label_mapping.txt", "r") as f:
            for line in f:
                name, id = line.strip().split(',')
                label_map[int(id)] = name
    face_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    return recognizer, label_map, face_cascade

recognizer, label_map, face_cascade = load_recognizer()

def main():
    st.title("Face Recognition Attendance System")
    col1, col2 = st.columns([2, 1])
    camera_placeholder = col1.empty()
    feedback_placeholder = col2.empty()
    marked_list_placeholder = col2.empty()

    start_button = col2.button("Start Camera")
    stop_button = col2.button("Stop Camera")

    if start_button:
        st.session_state.camera_running = True
    if stop_button:
        st.session_state.camera_running = False

    if st.session_state.camera_running:
        cap = cv2.VideoCapture(0)
        while st.session_state.camera_running:
            ret, frame = cap.read()
            if not ret:
                st.warning("Unable to access webcam.")
                break

            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))

            recognized_name = None
            for (x, y, w, h) in faces:
                size = max(w, h)
                center_x, center_y = x + w//2, y + h//2
                x_new = max(center_x - size//2, 0)
                y_new = max(center_y - size//2, 0)
                x_new = min(x_new, gray.shape[1] - size)
                y_new = min(y_new, gray.shape[0] - size)

                face_roi = gray[y_new:y_new + size, x_new:x_new + size]
                try:
                    label, confidence = recognizer.predict(face_roi)
                    if confidence < 70 and label in label_map:
                        recognized_name = label_map[label]
                    else:
                        recognized_name = "Unknown"
                except:
                    recognized_name = "Unknown"

                cv2.rectangle(rgb_frame, (x_new, y_new), (x_new + size, y_new + size), (0, 255, 0), 2)
                cv2.putText(rgb_frame, recognized_name, (x_new, y_new - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

            camera_placeholder.image(rgb_frame, channels="RGB", use_column_width=True, caption="Live Camera Feed")
            
            if recognized_name:
                if recognized_name != "Unknown":
                    feedback_placeholder.success(f"✅ Welcome, {recognized_name}!")
                else:
                    feedback_placeholder.error("❌ Face not recognized")

            if st.session_state.last_access:
                access = st.session_state.last_access
                status = "✅ Granted" if access["status"] == "granted" else "❌ Denied"
                col2.markdown(f"""
                    **Last Access Attempt**
                    - Name: {access['name']}
                    - Status: {status}
                    - Time: {access['timestamp']}
                """)

            time.sleep(0.03)
        cap.release()

if __name__ == "__main__":
    main()