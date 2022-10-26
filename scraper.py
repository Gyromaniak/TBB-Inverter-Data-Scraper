import datetime
import io
import json
import time
import requests
from requests_html import HTMLSession

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
    session = HTMLSession()
    data = {
        "Authorization": token
    }

    r = session.get(url,
                    headers=data)
    r.html.render()
    fix_bytes_value = r.content.replace(b"'", b'"')
    return json.load(io.BytesIO(fix_bytes_value))


def get_tbb_data_from_graph(token, site_id, date):
    session = HTMLSession()
    data = {
        "Authorization": token
    }

    graph_data_url = config.tbb_graph_base_url + f"?id={site_id}&dayTime={date}&interval=60"
    r = session.get(graph_data_url,
                    headers=data)
    r.html.render()
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


token_ = get_tbb_token()

sites = get_sites(token_)
for site in sites['data']:
    print(json.dumps(site, indent=4))

site_to_query = credentials.tbb_site_id  # You can get your site ID from the request above.

c = mqtt_integration.connect_mqtt()

state = None

while True:
    tbb_data = get_tbb_data_from_sites(token_, site_to_query, datetime.datetime.now().strftime("%Y-%m-%d"))
    charge_rate = float(tbb_data['solar_yield']) - float(tbb_data['consumption'])
    soc = float(tbb_data['battery_soc'])
    print(f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Battery SOC: {tbb_data['battery_soc']}%"
          f" | Solar Yield: {tbb_data['solar_yield']} W"
          f" | Load: {tbb_data['consumption']} W"
          f" | Charge Rate: {charge_rate} W")
    if charge_rate > 0:
        if soc > 98 and charge_rate > 0:
            if state != "surplus":
                state = "surplus"
                mqtt_integration.publish(c, state)
        if state != "charging":
            state = "charging"
            mqtt_integration.publish(c, state)
    else:
        if state != "discharging":
            state = "discharging"
            mqtt_integration.publish(c, state)

    time.sleep(10)
