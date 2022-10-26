import random
import credentials
from paho.mqtt import client as mqtt_client

client_id = f'python-mqtt-{random.randint(0, 1000)}'


def connect_mqtt():
    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            print("Connected to MQTT Broker!")
        else:
            print("Failed to connect, return code %d\n", rc)

    # Set Connecting Client ID

    client = mqtt_client.Client(client_id)
    client.username_pw_set(credentials.mqtt_username, credentials.mqtt_password)
    client.on_connect = on_connect
    client.connect(credentials.mqtt_broker, credentials.mqtt_port)
    return client


def publish(client, msg):
    result = client.publish(credentials.mqtt_topic, msg)
    status = result[0]
    if status == 0:
        print(f"Sent message `{msg}` to topic `{credentials.mqtt_topic}`")
    else:
        print(f"Failed to send message `{msg}` to topic {credentials.mqtt_topic}")
