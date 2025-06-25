import streamlit as st
from PIL import Image
from ultralytics import YOLO
import os

# Load the trained model
model = YOLO("yolov8n.pt")  # or "best.pt" if you've trained a model

st.title("🚗 Vehicle Detection App")

uploaded_file = st.file_uploader("Upload an image", type=["jpg", "png", "jpeg"])
if uploaded_file:
    image = Image.open(uploaded_file)
    st.image(image, caption="Uploaded Image", use_column_width=True)

    # Run detection
    with st.spinner("Detecting..."):
        results = model.predict(image)

    # Show results
    res_plotted = results[0].plot()
    st.image(res_plotted, caption="Detected Vehicles")
