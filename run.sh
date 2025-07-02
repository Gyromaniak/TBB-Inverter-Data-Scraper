#!/usr/bin/with-contenv bashio

echo "Starting..."

while true; do
    python3 /app/scraper.py
    exit_code=$?
    echo "scraper.py exited with code ${exit_code}. Restarting in 5 seconds..." >&2
    sleep 5
done
