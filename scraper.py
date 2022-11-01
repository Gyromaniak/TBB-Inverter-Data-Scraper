import datetime
import time

import credentials
import config
import mqtt_integration as mqtt

from tbb_integrations import TBB

if __name__ == '__main__':
    tbb = TBB(config, credentials)
    sites = tbb.sites
    for site in sites['data']:
        print("You have access to site: " + site['name'] + " with ID: " + str(site['id']))

    site_to_query = credentials.tbb_site_id
    print("\nUsing Site ID: " + str(site_to_query))

    tbb_summary_data = tbb.get_tbb_day_summary(site_to_query, datetime.datetime.now().strftime("%Y-%m-%d"))
    daily_summary = f"""\nDay Summary:
    AC Load: {tbb_summary_data['acout']} kWh
    AC In: {tbb_summary_data['acin']} kWh
    Solar: {tbb_summary_data['solar']} kWh
    AC Feedback: {tbb_summary_data['adfeedback']} kWh
    """
    print(daily_summary)

    summary_ac_load = tbb_summary_data['acout']
    summary_ac_in = tbb_summary_data['acin']
    summary_solar = tbb_summary_data['solar']
    summary_ac_feedback = tbb_summary_data['adfeedback']

    client = mqtt.connect_mqtt()
    mqtt.publish_discovery_messages(client)

    print("Collecting data every 10 seconds. Press Ctrl+C to stop.")
    print("####################################################")

    while True:
        tbb_data = tbb.get_tbb_data_from_sites(site_to_query)

        alarm_state = "ON" if tbb_data["alarm_status"] != 0 else "OFF"

        load = float(tbb_data['consumption'])
        pv_power = float(tbb_data['solar_yield']) / 1000
        dc_voltage = float(tbb_data['dc_voltage'])
        grid_power = float(tbb_data['ac_source']) / 1000
        battery_soc = float(tbb_data['battery_soc'])

        mqtt.publish("homeassistant/tbb-scraper/problem/state", client, alarm_state)
        mqtt.publish("homeassistant/tbb-scraper/soc/state", client, battery_soc)
        mqtt.publish("homeassistant/tbb-scraper/load/state", client, load)
        mqtt.publish("homeassistant/tbb-scraper/pvPower/state", client, pv_power)
        mqtt.publish("homeassistant/tbb-scraper/gridPower/state", client, grid_power)
        mqtt.publish("homeassistant/tbb-scraper/battPower/state", client, round(load / 1000 - pv_power - grid_power,3))

        mqtt.publish("homeassistant/tbb-scraper/pv/state", client, summary_solar)
        mqtt.publish("homeassistant/tbb-scraper/export/state", client, 0)  # Blerrie Eskom
        mqtt.publish("homeassistant/tbb-scraper/import/state", client, summary_ac_in)

        if pv_power - load > 0:
            mqtt.publish("homeassistant/tbb-scraper/discharge/state", client, 0)
            mqtt.publish("homeassistant/tbb-scraper/charge/state", client, round(pv_power - load / 1000,3))
        else:
            mqtt.publish("homeassistant/tbb-scraper/discharge/state", client, round(pv_power - load / 1000,3))
            mqtt.publish("homeassistant/tbb-scraper/charge/state", client, 0)

        print(f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - SOC: {tbb_data['battery_soc']}%"
              f" | Solar Yield: {pv_power} kWh"
              f" | Load: {load} W"
              f" | Surplus: {pv_power - load/1000} kWh"
              f" | Alarm State: {alarm_state}")

        time.sleep(10)
