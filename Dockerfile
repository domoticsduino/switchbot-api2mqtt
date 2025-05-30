# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY switchbot_api2mqtt.py .
COPY .env .

# Default command
CMD ["python", "switchbot_api2mqtt.py"]
