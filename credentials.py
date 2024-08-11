import os

tbb_username = os.getenv("TBB_USERNAME")
tbb_password = os.getenv("TBB_PASSWORD")
tbb_site_id = os.getenv("TBB_SITE_ID")

mqtt_username = os.getenv("MQTT_USERNAME")
mqtt_password = os.getenv("MQTT_PASSWORD")
mqtt_broker = os.getenv("MQTT_BROKER")
mqtt_port = os.getenv("MQTT_PORT")
mqtt_topic = os.getenv("MQTT_TOPIC")


if not tbb_username:
    raise Exception("TBB_USERNAME environment variable not set.")

if not tbb_password:
    raise Exception("TBB_PASSWORD environment variable not set.")

if not tbb_site_id:
    raise Exception("TBB_SITE_ID environment variable not set.")

if not mqtt_username:
    raise Exception("MQTT_USERNAME environment variable not set.")

if not mqtt_password:
    raise Exception("MQTT_PASSWORD environment variable not set.")

if not mqtt_broker:
    raise Exception("MQTT_BROKER environment variable not set.")

if not mqtt_port:
    raise Exception("MQTT_PORT environment variable not set.")

if not mqtt_topic:
    raise Exception("MQTT_TOPIC environment variable not set.")





