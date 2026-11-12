# TBB-Inverter-Data-Scraper
Collect TBB inverter data by means of Python request scraping.
# Example Output
![img.png](example_output.png)

# Deployment
Runs as a Docker Compose service. Settings come from a `.env` file next to `docker-compose.yml`
(`TBB_USERNAME`, `TBB_PASSWORD`, `TBB_SITE_ID`, `MQTT_BROKER`, `MQTT_PORT`, `MQTT_TOPIC`, `MQTT_USERNAME`, `MQTT_PASSWORD`).

```sh
git pull
docker compose up -d --build
```

Deploys are manual for now: the previous GitHub Actions workflow logged in over SSH with a password
through a port forward that no longer exists, so it was removed.

# Home Assistant
Entities are announced through MQTT discovery. The discovery messages are retained and are also
republished whenever the scraper (re)connects to the broker or Home Assistant reports `online`
on `homeassistant/status`, so the entities survive a Home Assistant or broker restart.
