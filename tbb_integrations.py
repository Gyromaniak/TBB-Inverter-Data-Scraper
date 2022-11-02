import datetime
import io
import json
import uuid
import datetime
import requests
from websocket import create_connection


class TBB:
    def __init__(self, config, credentials):
        self.config = config
        self.credentials = credentials
        self.token = self.get_tbb_token()
        self.sites = self.get_sites()
        self.insta_charge_last_pressed = None
        self.selected_site_number = None
        self.selected_equipment_number = None

    def get_tbb_token(self):
        url = self.config.tbb_login_url
        headers = {
            "Content-Type": "application/json;charset=UTF-8",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.113 Safari/537.36"
        }
        body = {
            'account': self.credentials.tbb_username,
            'password': self.credentials.tbb_password
        }
        html = requests.post(url, data=json.dumps(body),
                             headers=headers).content
        fix_bytes_value = html.replace(b"'", b'"')
        my_json = json.load(io.BytesIO(fix_bytes_value))
        token = my_json["data"]["token"]

        if self.config.debug:
            print(f"Token Obtained: {token}")

        return token

    def get_sites(self):
        url = self.config.tbb_sites_url
        data = {
            "Authorization": self.token
        }
        r = requests.get(url,
                         headers=data)
        fix_bytes_value = r.content.replace(b"'", b'"')
        sites = json.load(io.BytesIO(fix_bytes_value))

        if self.config.debug:
            print(f"Sites Obtained: {sites}")

        return sites

    def get_tbb_data_from_graph(self, site_id, date):
        data = {
            "Authorization": self.token
        }

        graph_data_url = self.config.tbb_graph_base_url + f"?id={site_id}&dayTime={date}&interval=60"
        r = requests.get(graph_data_url, headers=data)
        fix_bytes_value = r.content.replace(b"'", b'"')
        my_json = json.load(io.BytesIO(fix_bytes_value))
        inverter_data = my_json["data"]

        # loop through response and get the latest wattage in the graph that is not null.
        # invert the array
        reversed_ = inverter_data[::-1]
        last_record = None
        for data in reversed_:
            if data['solar']:
                last_record = data
                break
        cleaned_record = {
            "time": datetime.datetime.fromtimestamp(last_record['datetime']),
            "tbb_data": last_record
        }

        if self.config.debug:
            print(f"Graph Data Obtained: {cleaned_record}")

        return cleaned_record

    def get_tbb_data_from_sites(self, site_id):
        sites = self.get_sites()

        site_data = [site for site in sites['data'] if site['id'] == site_id][0]

        if self.config.debug:
            print(f"Site Data Obtained: {site_data}")

        return site_data

    def get_tbb_day_summary(self, site_id, date):
        data = {
            "Authorization": self.token
        }

        graph_data_url = self.config.tbb_summary_base_url + f"?id={site_id}&dayTime={date}"
        r = requests.get(graph_data_url, headers=data)
        fix_bytes_value = r.content.replace(b"'", b'"')
        my_json = json.load(io.BytesIO(fix_bytes_value))
        summary_data = my_json["data"]
        summary_data_kwh = {
            "acout": summary_data["acout"]["val"] / 1000 if summary_data["acout"]["symbol"] == "Wh" else
            summary_data["acout"]["val"],
            "acin": summary_data["acin"]["val"] / 1000 if summary_data["acin"]["symbol"] == "Wh" else
            summary_data["acin"]["val"],
            "solar": summary_data["solar"]["val"] / 1000 if summary_data["solar"]["symbol"] == "Wh" else
            summary_data["solar"]["val"],
            "adfeedback": summary_data["adfeedback"]["val"] / 1000 if summary_data["adfeedback"]["symbol"] == "Wh" else
            summary_data["adfeedback"]["val"]
        }

        if self.config.debug:
            print(f"Summary Data Obtained: {summary_data_kwh}")

        return summary_data_kwh

    def send_charge_command(self, equipment_number):

        if not self.insta_charge_last_pressed or (datetime.datetime.now() - self.insta_charge_last_pressed).seconds > 180:
            self.insta_charge_last_pressed = datetime.datetime.now()

            if self.config.debug:
                print("Not sending charge command as debug is enabled.")
                return True
            ws = create_connection(f"ws://8.210.132.188:10250/websocket/equipment/{equipment_number}")

            print("Sending Authentication message")
            auth_message = {
                "uuid": str(uuid.uuid4()),
                "cmd": 272,
                "lang": "en",
                "data": {
                    "token": self.token}
            }
            ws.send(json.dumps(auth_message))
            print("Sent")
            print("Receiving...")
            result = ws.recv()
            print("Received '%s'" % result)
            result = ws.recv()
            print("Sending trigger Charge message")
            trigger_charge_message = {"uuid": str(uuid.uuid4()),
                                      "cmd": 320,
                                      "tag": 9,
                                      "data": {"address": "00331103F3", "val": "1", "symbol": ""}
                                      }

            ws.send(json.dumps(trigger_charge_message))
            print("Sent")
            print("Receiving...")
            result = ws.recv()
            print("Received '%s'" % result)

            ws.close()
        else:
            print("Last pressed was less than 3 minutes ago. Not sending command.")
