import datetime
import io
import json
import time
import requests

# Local Imports
import credentials
import config
import mqtt_integration


def get_tbb_token():
    url = config.tbb_login_url
    headers = {
        "Content-Type": "application/json;charset=UTF-8",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.113 Safari/537.36"
    }
    body = {
        'account': credentials.tbb_username,
        'password': credentials.tbb_password
    }
    html = requests.post(url, data=json.dumps(body),
                         headers=headers).content
    fix_bytes_value = html.replace(b"'", b'"')
    my_json = json.load(io.BytesIO(fix_bytes_value))
    token = my_json["data"]["token"]
    return token


def get_sites(token):
    url = config.tbb_sites_url
    data = {
        "Authorization": token
    }
    r = requests.get(url,
                     headers=data)
    fix_bytes_value = r.content.replace(b"'", b'"')
    return json.load(io.BytesIO(fix_bytes_value))


def get_tbb_data_from_graph(token, site_id, date):
    data = {
        "Authorization": token
    }

    graph_data_url = config.tbb_graph_base_url + f"?id={site_id}&dayTime={date}&interval=60"
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
    return cleaned_record


def get_tbb_data_from_sites(token, site_id, date):
    sites = get_sites(token)
    # Get Sites where ID is site_id
    # TODO: error handling
    return [site for site in sites['data'] if site['id'] == site_id][0]


def get_tbb_day_summary(token, site_id, date):
    data = {
        "Authorization": token
    }

    graph_data_url = config.tbb_summary_base_url + f"?id={site_id}&dayTime={date}"
    r = requests.get(graph_data_url, headers=data)
    fix_bytes_value = r.content.replace(b"'", b'"')
    my_json = json.load(io.BytesIO(fix_bytes_value))
    summary_data = my_json["data"]
    summary_data_kwh = {
        "acout": summary_data["acout"]["val"] / 1000 if summary_data["acout"]["symbol"] == "Wh" else summary_data["acout"]["val"],
        "acin": summary_data["acin"]["val"] / 1000 if summary_data["acin"]["symbol"] == "Wh" else summary_data["acin"]["val"],
        "solar": summary_data["solar"]["val"] / 1000 if summary_data["solar"]["symbol"] == "Wh" else summary_data["solar"]["val"],
        "adfeedback": summary_data["adfeedback"]["val"] / 1000 if summary_data["adfeedback"]["symbol"] == "Wh" else summary_data["adfeedback"]["val"]
    }
    return summary_data_kwh


token_ = get_tbb_token()

sites = get_sites(token_)
for site in sites['data']:
    print("You have access to site: " + site['name'] + " with ID: " + str(site['id']))


site_to_query = credentials.tbb_site_id  # You can get your site ID from the request above.
print("\nUsing Site ID: " + str(site_to_query))
c = mqtt_integration.connect_mqtt()

state = None

tbb_summary_data = get_tbb_day_summary(token_, site_to_query, datetime.datetime.now().strftime("%Y-%m-%d"))
daily_summary = f"""\nDay Summary:
AC Load: {tbb_summary_data['acout']} kWh
AC In: {tbb_summary_data['acin']} kWh
Solar: {tbb_summary_data['solar']} kWh
AC Feedback: {tbb_summary_data['adfeedback']} kWh
"""
print(daily_summary)

# TODO:
# Publish to MQTT

print("Collecting data every 10 seconds. Press Ctrl+C to stop.")
print("####################################################")
while True:
    tbb_data = get_tbb_data_from_sites(token_, site_to_query, datetime.datetime.now().strftime("%Y-%m-%d"))

    load = float(tbb_data['consumption'])
    pv_power = float(tbb_data['solar_yield'])
    dc_voltage = float(tbb_data['dc_voltage'])
    grid_power = float(tbb_data['consumption'])
    battery_soc = float(tbb_data['battery_soc'])

    # TODO:
    # Publish to MQTT

    print(f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Battery SOC: {tbb_data['battery_soc']}%"
          f" | Solar Yield: {tbb_data['solar_yield']} W"
          f" | Load: {tbb_data['consumption']} W")

    time.sleep(10)
