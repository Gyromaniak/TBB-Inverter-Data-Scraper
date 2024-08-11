FROM python:3.10-slim

RUN pip3 install --no-cache-dir --disable-pip-version-check paho-mqtt~=1.6.1 requests~=2.28.1 websocket-client~=1.4.1

WORKDIR /app

COPY . ./

RUN ls -la /app

RUN echo "Starting..." && \
    python3 /app/scraper.py