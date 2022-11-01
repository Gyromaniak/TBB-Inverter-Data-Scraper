import random
import config
from paho.mqtt import client as mqtt_client

import credentials

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


def publish(topic, client, msg):
    result = client.publish(topic, msg)
    status = result[0]

    if not config.debug:
        return

    if status == 0:
        print(f"Sent message `{msg}` to topic `{topic}`")
    else:
        print(f"Failed to send message `{msg}` to topic {topic}")


def get_binary_sensor_mqtt_config_message(device_class, group_name, entity_name, friendly_name):
    template = f"""
    {{
        "unique_id": "binary_sensor.{group_name}-{entity_name}",
        "name": "TBB {friendly_name}",
        "state_topic": "homeassistant/{group_name}/{entity_name}/state",
        "device_class": "{device_class}"
    }}
    """

    return template


def get_mqtt_config_message(device_class, group_name, entity_name, friendly_name, unit_of_measurement,
                            measurement=True):
    state_class = "measurement" if measurement else "total_increasing"
    template = f"""
    {{
        "unique_id": "sensor.{group_name}-{entity_name}",
        "name": "TBB {friendly_name}",
        "state_topic": "homeassistant/{group_name}/{entity_name}/state",
        "unit_of_measurement": "{unit_of_measurement}",
        "device_class": "{device_class}",
        "state_class": "{state_class}"
    }}
    """

    return template


def publish_discovery_messages(client):
    problem_config_message = get_binary_sensor_mqtt_config_message("power", "tbb-scraper", "problem", "Problem")

    soc_config_message = get_mqtt_config_message("battery", "tbb-scraper", "soc", "Battery", "%")
    load_config_message = get_mqtt_config_message("power", "tbb-scraper", "load", "Load", "W")
    pv_power_config_message = get_mqtt_config_message("power", "tbb-scraper", "pvPower", "PV Power", "W")
    grid_power_config_message = get_mqtt_config_message("power", "tbb-scraper", "gridPower", "Grid Power", "W")
    batt_power_config_message = get_mqtt_config_message("power", "tbb-scraper", "battPower", "Battery Power", "W")
    batt_charge_power_config_message = get_mqtt_config_message("power", "tbb-scraper", "battChargePower", "Battery Charge Power", "W")
    batt_discharge_power_config_message = get_mqtt_config_message("power", "tbb-scraper", "battDischargePower", "Battery Discharge Power", "W")

    pv_energy_config_message = get_mqtt_config_message("energy", "tbb-scraper", "pv", "PV Energy", "kWh",
                                                       measurement=False)
    export_energy_config_message = get_mqtt_config_message("energy", "tbb-scraper", "export", "Export Energy",
                                                           "kWh", measurement=False)
    import_energy_config_message = get_mqtt_config_message("energy", "tbb-scraper", "import", "Import Energy",
                                                           "kWh", measurement=False)
    discharge_energy_config_message = get_mqtt_config_message("energy", "tbb-scraper", "discharge",
                                                              "Discharge Energy", "kWh", measurement=False)
    charge_energy_config_message = get_mqtt_config_message("energy", "tbb-scraper", "charge", "Charge Energy",
                                                           "kWh", measurement=False)
    load_energy_config_message = get_mqtt_config_message("energy", "tbb-scraper", "loadEnergy", "Load Energy", "kWh",
                                                         measurement=False)

    publish(f"homeassistant/binary_sensor/tbb-scraper/problem/config", client, problem_config_message)

    publish(f"homeassistant/sensor/tbb-scraper/soc/config", client, soc_config_message)
    publish(f"homeassistant/sensor/tbb-scraper/load/config", client, load_config_message)
    publish(f"homeassistant/sensor/tbb-scraper/pvPower/config", client, pv_power_config_message)
    publish(f"homeassistant/sensor/tbb-scraper/gridPower/config", client, grid_power_config_message)
    publish(f"homeassistant/sensor/tbb-scraper/battPower/config", client, batt_power_config_message)
    publish(f"homeassistant/sensor/tbb-scraper/battChargePower/config", client, batt_charge_power_config_message)
    publish(f"homeassistant/sensor/tbb-scraper/battDischargePower/config", client, batt_discharge_power_config_message)

    publish(f"homeassistant/sensor/tbb-scraper/pv/config", client, pv_energy_config_message)
    publish(f"homeassistant/sensor/tbb-scraper/export/config", client, export_energy_config_message)
    publish(f"homeassistant/sensor/tbb-scraper/import/config", client, import_energy_config_message)
    publish(f"homeassistant/sensor/tbb-scraper/discharge/config", client, discharge_energy_config_message)
    publish(f"homeassistant/sensor/tbb-scraper/charge/config", client, charge_energy_config_message)
    publish(f"homeassistant/sensor/tbb-scraper/loadEnergy/config", client, load_energy_config_message)
