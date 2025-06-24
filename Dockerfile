# Use official Python image
FROM python:3.10-slim

# Set the working directory inside the container
WORKDIR /app

# Copy only required files
COPY requirements.txt ./
COPY app.py ./
COPY main.py ./
COPY yolov8n.pt ./
COPY templates ./templates

RUN ls -la

COPY db_copy.db ./vehicle_data.db

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose Flask's default port
EXPOSE 5000

# Run the Flask app
CMD ["python", "app.py"]
