import asyncio
import datetime
import time

import config
import credentials
import mqtt_integration as mqtt
from mqtt_handler import MQTTHandler
from tbb_integrations import TBB


def get_daily_summary(site_to_query, tbb):
    tbb_summary_data = tbb.get_tbb_day_summary(site_to_query, datetime.datetime.now().strftime("%Y-%m-%d"))
    return tbb_summary_data


def consume_and_publish_power_stats(client, tbb_data):
    alarm_state = "ON" if tbb_data["alarm_status"] != 0 else "OFF"
    load = float(tbb_data['consumption'])  # load in W
    pv_power = float(tbb_data['solar_yield'])  # pv_power in W
    dc_voltage = float(tbb_data['dc_voltage'])  # dc_voltage in V
    grid_power = float(tbb_data['ac_source'])  # grid_power in W
    battery_soc = float(tbb_data['battery_soc'])  # battery_soc in %
    battery_power = round(load - pv_power - grid_power, 3)  # battery_power in W

    mqtt.publish("homeassistant/tbb-scraper/problem/state", client, alarm_state)
    mqtt.publish("homeassistant/tbb-scraper/soc/state", client, battery_soc)
    mqtt.publish("homeassistant/tbb-scraper/load/state", client, load)
    mqtt.publish("homeassistant/tbb-scraper/pvPower/state", client, pv_power)
    mqtt.publish("homeassistant/tbb-scraper/gridPower/state", client, grid_power)
    mqtt.publish("homeassistant/tbb-scraper/battPower/state", client, battery_power)
    if battery_power > 0:
        mqtt.publish("homeassistant/tbb-scraper/battDischargePower/state", client, abs(battery_power))
    if battery_power < 0:
        mqtt.publish("homeassistant/tbb-scraper/battChargePower/state", client, abs(battery_power))


def consume_and_publish_energy_stats(client, tbb_summary_data):
    summary_ac_load = tbb_summary_data['acout']  # never gets used by any HA sensor, whats dis?
    summary_ac_in = tbb_summary_data['acin']
    summary_solar = tbb_summary_data['solar']
    summary_ac_feedback = tbb_summary_data['adfeedback']

    # this _may_ be our charge stat, given that we never feed back to the grid
    solar_load_delta = round(tbb_summary_data['solar'] - tbb_summary_data['acout'], 2)

    # the delta between solar and acout is the amount of energy going into the battery if positive
    # if negative, then the battery is discharging
    # by how much, we also need to consider the grid in order to figure out how much
    # discharge energy = acin - acout - solar ? maybe
    # depends on what AC In actually is, current stats have me confused

    charge_energy = solar_load_delta if solar_load_delta > 0 else 0  # will be in kWh
    # DOES NOT CONSIDER EXCESS CHARGING FROM THE GRID!

    mqtt.publish("homeassistant/tbb-scraper/pv/state", client, summary_solar)
    mqtt.publish("homeassistant/tbb-scraper/export/state", client, summary_ac_feedback)
    mqtt.publish("homeassistant/tbb-scraper/import/state", client, summary_ac_in)
    mqtt.publish("homeassistant/tbb-scraper/loadEnergy/state", client, summary_ac_load)

    # battery charge / discharge is not available on source data
    # we have to compute it from the other values
    # summary_battery_charge = summary_ac_in - summary_solar
    # summary_battery_discharge = summary_ac_load - summary_ac_feedback
    # maybe? unsure

    # We can't calculate discharge and charge from Watt values. They contain no concept of time
    # We will need to use the energy stats available to us in order to do that.
    # if pv_power - load > 0:
    #     mqtt.publish("homeassistant/tbb-scraper/discharge/state", client, 0)
    #     mqtt.publish("homeassistant/tbb-scraper/charge/state", client, round(pv_power - load / 1000,3))
    # else:
    #     mqtt.publish("homeassistant/tbb-scraper/discharge/state", client, round(pv_power - load / 1000,3))
    #     mqtt.publish("homeassistant/tbb-scraper/charge/state", client, 0)


def print_current_system_state(tbb_data):
    alarm_state = "ON" if tbb_data["alarm_status"] != 0 else "OFF"
    load = float(tbb_data['consumption'])  # load in W
    pv_power = float(tbb_data['solar_yield'])  # pv_power in W
    dc_voltage = float(tbb_data['dc_voltage'])  # dc_voltage in V
    grid_power = float(tbb_data['ac_source'])  # grid_power in W
    battery_soc = float(tbb_data['battery_soc'])  # battery_soc in %
    battery_power = round(load - pv_power - grid_power, 3)  # battery_power in W

    print(f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
          f" | Power Summary"
          f" | SOC: {battery_soc}%"
          f" | Solar Yield: {pv_power} W"
          f" | Load: {load} W"
          f" | Surplus: {pv_power - load} W"  # should be == to battery power in the inverse
          f" | Grid: {grid_power} W"
          f" | Alarm State: {alarm_state}"
          f" | Battery Power: {battery_power} W"
          f" | DC Voltage: {dc_voltage} V")


def print_daily_stats_thus_far(tbb_summary_data):
    # this _may_ be our charge stat, given that we never feed back to the grid
    solar_load_delta = round(tbb_summary_data['solar'] - tbb_summary_data['acout'], 2)
    print(f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
          f" | Energy Summary"
          f" | AC Load: {tbb_summary_data['acout']} kWh"
          f" | AC In: {tbb_summary_data['acin']} kWh"
          f" | Solar: {tbb_summary_data['solar']} kWh"
          f" | Solar - Load delta: {solar_load_delta} kWh"
          f" | AC Feedback: {tbb_summary_data['adfeedback']} kWh"
          )


async def main():

    if config.debug:
        print("Debug mode enabled. Charge command will not work!")

    tbb = TBB(config, credentials)
    sites = tbb.sites
    for site in sites['data']:
        print("You have access to site: " + site['name'] + " with ID: " + str(site['id']))

    site_to_query = credentials.tbb_site_id
    print("\nUsing Site ID: " + str(site_to_query))

    client = await mqtt.connect_mqtt()
    mqtt.publish_discovery_messages(client)
    mqtt_handler = MQTTHandler(client, tbb, config)
    mqtt_handler.subscribe_to_command_topics()

    print("Collecting power data every 10 seconds. Press Ctrl+C to stop.")
    print("####################################################")

    while True:
        tbb_data = tbb.get_tbb_data_from_sites(site_to_query)
        consume_and_publish_power_stats(client, tbb_data)

        tbb_summary_data = get_daily_summary(site_to_query, tbb)
        consume_and_publish_energy_stats(client, tbb_summary_data)

        print_current_system_state(tbb_data)
        print_daily_stats_thus_far(tbb_summary_data)

        await asyncio.sleep(10)


if __name__ == '__main__':
    asyncio.run(main())
