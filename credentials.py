import os

tbb_username = os.getenv("TBB_USERNAME")
tbb_password = os.getenv("TBB_PASSWORD")
tbb_site_id = os.getenv("TBB_SITE_ID")

mqtt_username = os.getenv("MQTT_USERNAME")
mqtt_password = os.getenv("MQTT_PASSWORD")
mqtt_broker = os.getenv("MQTT_BROKER")
mqtt_port = os.getenv("MQTT_PORT")
mqtt_topic = os.getenv("MQTT_TOPIC")


for var_name, var_value in locals().copy().items():
    if "mqtt_" in var_name or "tbb_" in var_name:
        if var_value is None:
            raise ValueError(f"{var_name} environment variable is not set.")



