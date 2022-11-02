


class MQTTHandler(object):

    def __init__(self, client, tbb_integration, config):
        self.client = client
        self.tbb = tbb_integration
        self.config = config

    def handle_charge_button_press(self):
        print("Handling charge button press.")
        print("####################")
        self.tbb.send_charge_command(self.tbb.equipment_number)
        print("####################")

    def on_mqtt_command_message_received(self, client, userdata, message):
        button = message.topic.split("/")[-2]

        if self.config.debug:
            print("[[ MESSAGE RECEIVED ]] ", str(message.payload.decode("utf-8")))
            print("[[ TOPIC ]] ", message.topic)
            print("[[ BUTTON ]] ", button)

        if button == "charge-button":
            self.handle_charge_button_press()
        else:
            print(f"Unknown button pressed: {button}")

    def subscribe_to_command_topics(self):
        self.client.on_message = self.on_mqtt_command_message_received
        self.client.subscribe("homeassistant/+/tbb-scraper/+/commands")
