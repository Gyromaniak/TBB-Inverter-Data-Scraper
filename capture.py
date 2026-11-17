"""Records everything TBB reports about the site, raw, so the values can be studied later.

Runs as its own process next to the scraper and publishes nothing about the inverter.
Each line of capture-data/YYYY-MM-DD.jsonl is one JSON record:

  {"t": "<local time>", "src": "<source>", "why": "<change|interval|...>", "data": ...}

Sources
  rest      the site record from the REST API (what the scraper itself reads)
  events    the active alarm/fault list from the live feed
  realdata  live readings from the live feed, as {address: [value, unit]}
  tree      the equipment list sent after login to the live feed
  ws        any other live-feed message, unmodified
  note      a marker typed into the "TBB capture note" entity in Home Assistant
  info      capture start/stop, reconnects and errors

Records are written when something changes, and at a fixed interval even when nothing does.
"""
import datetime
import json
import os
import threading
import time
import traceback

import requests
from paho.mqtt import client as mqtt_client

import config
import credentials
import nova_live

DATA_DIR = os.getenv("CAPTURE_DIR", "capture-data")
REST_POLL_SECONDS = 10
REST_FULL_SECONDS = 60
REALDATA_REQUEST_SECONDS = 10
REALDATA_FULL_SECONDS = 30
EVENTS_FULL_SECONDS = 300
RELOGIN_SECONDS = 6 * 3600

# Left out of the capture: who and where, not how the inverter is doing.
REST_PRIVATE_FIELDS = ("name", "latitude", "longitude", "location", "creator", "administer", "websocket_address",
                       "websocket_ssl_address", "banner_text", "banner_images", "banner_text_phone",
                       "banner_image_phone")
# A change in any of these writes a record straight away.
REST_STATE_FIELDS = ("alarm_status", "alarm_remind", "running_type", "battery_status", "online", "system_mode",
                     "work_model", "eventInfos", "system_config")

NOTE_COMMAND_TOPIC = "homeassistant/text/tbb-scraper/capture-note/commands"
NOTE_STATE_TOPIC = "homeassistant/text/tbb-scraper/capture-note/state"
NOTE_CONFIG_TOPIC = "homeassistant/text/tbb-scraper/capture-note/config"

_write_lock = threading.Lock()


def record(src, why, data):
    now = datetime.datetime.now()
    line = json.dumps({"t": now.strftime("%Y-%m-%d %H:%M:%S"), "src": src, "why": why, "data": data},
                      ensure_ascii=False, separators=(",", ":"))
    with _write_lock:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(os.path.join(DATA_DIR, now.strftime("%Y-%m-%d") + ".jsonl"), "a", encoding="utf-8") as f:
            f.write(line + "\n")


def info(text):
    print(f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | {text}", flush=True)
    record("info", "", text)


class Session:
    """A TBB login shared by the REST poller and the live feed."""

    def __init__(self):
        self._lock = threading.Lock()
        self.token = None
        self.public_key = None
        self.logged_in_at = 0

    def get(self, force=False):
        with self._lock:
            if force or not self.token or time.time() - self.logged_in_at > RELOGIN_SECONDS:
                self.token, self.public_key = nova_live.login(config.tbb_login_url, credentials.tbb_username,
                                                              credentials.tbb_password)
                self.logged_in_at = time.time()
            return self.token, self.public_key

    def site(self):
        token, _ = self.get()
        reply = requests.get(config.tbb_sites_url, headers={"Authorization": token}, timeout=30).json()
        if reply.get("code") != 200:
            self.get(force=True)
            raise RuntimeError(f"site list returned code {reply.get('code')}: {reply.get('message')}")
        return [s for s in reply["data"] if s["id"] == credentials.tbb_site_id][0]


def rest_loop(session):
    last_state, last_full = None, 0
    while True:
        try:
            site = session.site()
            state = {k: site.get(k) for k in REST_STATE_FIELDS}
            state["grid_present"] = float(site.get("ac_source") or 0) != 0
            changed = state != last_state
            if changed or time.time() - last_full >= REST_FULL_SECONDS:
                record("rest", "change" if changed else "interval",
                       {k: v for k, v in site.items() if k not in REST_PRIVATE_FIELDS})
                last_state, last_full = state, time.time()
        except Exception as e:
            info(f"rest error: {type(e).__name__}: {e}")
        time.sleep(REST_POLL_SECONDS)


def live_loop(session):
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "nova_addresses.json")) as f:
        addresses = [a["address"] for a in json.load(f)]
    while True:
        feed = None
        try:
            token, public_key = session.get()
            feed = nova_live.NovaLive(session.site()["websocket_address"], token, public_key)
            feed.login()
            info("live feed connected")
            last_request = last_data_full = last_events_full = 0
            last_events = last_flags = None
            while True:
                if time.time() - session.logged_in_at > RELOGIN_SECONDS:
                    raise RuntimeError("session is old, logging in again")
                message = feed.receive()
                cmd, data = message.get("cmd"), message.get("data")
                if str(message.get("status")) not in ("200", "None"):
                    record("ws", "error", message)
                    if cmd == nova_live.CMD_LOGIN_RESPONSE:
                        session.get(force=True)
                        raise RuntimeError(f"live feed login refused: {message.get('message')}")
                elif cmd == nova_live.CMD_LOGIN_RESPONSE:
                    record("tree", "login", data)
                elif cmd == nova_live.CMD_REALEVENT_PUSH:
                    changed = data != last_events
                    if changed or time.time() - last_events_full >= EVENTS_FULL_SECONDS:
                        record("events", "change" if changed else "interval", data)
                        last_events, last_events_full = data, time.time()
                elif cmd == nova_live.CMD_REALDATA_RESPONSE and isinstance(data, list):
                    values = {d.get("address"): [d.get("val"), d.get("symbol")] for d in data}
                    # Values without a unit are states, flags and counters; a change in one is worth a record.
                    flags = {a: v[0] for a, v in values.items() if not v[1]}
                    changed = flags != last_flags
                    if changed or time.time() - last_data_full >= REALDATA_FULL_SECONDS:
                        record("realdata", "change" if changed else "interval", values)
                        last_flags, last_data_full = flags, time.time()
                elif cmd not in (nova_live.CMD_HEARTBEAT, nova_live.CMD_CONNECT, nova_live.CMD_REALDATA_PUSH):
                    record("ws", "other", message)
                if cmd != nova_live.CMD_CONNECT and time.time() - last_request >= REALDATA_REQUEST_SECONDS:
                    feed.request_real_data(addresses)
                    last_request = time.time()
        except Exception as e:
            info(f"live feed error: {type(e).__name__}: {e}")
            if not isinstance(e, (RuntimeError, OSError)):
                traceback.print_exc()
        finally:
            if feed:
                feed.close()
        time.sleep(15)


def start_notes():
    """A text entity in Home Assistant; whatever is typed into it lands in the capture as a marker."""

    def on_connect(client, userdata, flags, rc):
        if rc != 0:
            print(f"MQTT connect failed, return code {rc}", flush=True)
            return
        client.subscribe(NOTE_COMMAND_TOPIC)
        client.publish(NOTE_CONFIG_TOPIC, json.dumps({
            "unique_id": "text.tbb-capture-note", "name": "TBB capture note", "icon": "mdi:note-edit-outline",
            "command_topic": NOTE_COMMAND_TOPIC, "state_topic": NOTE_STATE_TOPIC, "max": 255}), retain=True)

    def on_message(client, userdata, message):
        note = message.payload.decode("utf-8", "replace").strip()
        if note:
            record("note", "", note)
            client.publish(NOTE_STATE_TOPIC, note, retain=True)
            print(f"note: {note}", flush=True)

    client = mqtt_client.Client(f"tbb-capture-{os.getpid()}")
    client.username_pw_set(credentials.mqtt_username, credentials.mqtt_password)
    client.on_connect, client.on_message = on_connect, on_message
    client.connect_async(credentials.mqtt_broker, credentials.mqtt_port)
    client.loop_start()


def main():
    info("capture starting")
    session = Session()
    try:
        start_notes()
    except Exception as e:
        info(f"notes unavailable: {type(e).__name__}: {e}")
    threading.Thread(target=rest_loop, args=(session,), daemon=True).start()
    live_loop(session)


if __name__ == "__main__":
    main()
