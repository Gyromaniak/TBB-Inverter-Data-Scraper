FROM python:3.10-slim

WORKDIR /app

# Install dependencies
RUN pip3 install --no-cache-dir paho-mqtt~=1.6.1 requests~=2.28.1 websocket-client~=1.4.1

# Copy the application code
COPY . .

# Ensure the script is executable
RUN chmod +x /app/run.sh

# Run the script
CMD ["/app/run.sh"]
