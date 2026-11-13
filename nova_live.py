"""Read-only client for the live feed that TBB's Nova web app uses.

The feed is a websocket. After login the server pushes the active alarm list ("real event")
every few seconds, and answers "real data" requests with the current readings for a list of
register addresses.

Only two requests are ever sent from here: login and the real-data read. The same connection
also accepts control and configuration writes (commands 320, 576, 832 and others); this module
deliberately has no way to send them.
"""
import base64
import json
import secrets
import time
import uuid

import requests
from Crypto.Cipher import AES, PKCS1_v1_5
from Crypto.PublicKey import RSA
from Crypto.Util.Padding import pad, unpad
from websocket import create_connection

CMD_HEARTBEAT = -1
CMD_CONNECT = 0
CMD_REALDATA_PUSH = 1  # "new readings are available", carries no data
CMD_REALEVENT_PUSH = 2  # the active alarm/fault list
CMD_STATUSDATA_PUSH = 3
CMD_LOGIN_REQUEST = 272
CMD_LOGIN_RESPONSE = 273
CMD_REALDATA_REQUEST = 288
CMD_REALDATA_RESPONSE = 289

_ALLOWED_REQUESTS = (CMD_LOGIN_REQUEST, CMD_REALDATA_REQUEST)

# Constants taken from the Nova web app. The login key is the app's built-in public key;
# every later request must use the per-account public key returned by the login API.
_LOGIN_PUBLIC_KEY = (
    "MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQCjqxUI2k36j47gJIUYioQk0K5LLmXmCP+ffPTsv7n1Za89dRMp60X4eYyKlfjNHIBiWMW9"
    "6cLxapM9ssp1mYHRYow0K6Ki2Udev4FjWeyxx79IJ27njE/WPePS5xr/LZHO4BL0JPj57UCg76bEmvlfzdqwJVIqlCvcNz2+A6JDzQIDAQAB"
)
_AES_IV = b"UTQMNP953UFXXKRG"
_KEY_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnoprstuvwxyz1234567890"


def login(login_url, username, password):
    """Log in over the REST API. Returns (token, account public key)."""
    headers = {"Content-Type": "application/json;charset=UTF-8", "user-agent": "Mozilla/5.0"}
    body = json.dumps({"account": username, "password": password})
    data = requests.post(login_url, data=body, headers=headers, timeout=30).json()["data"]
    return data["token"], data["userInfo"]["pubKey"]


class NovaLive:
    def __init__(self, websocket_url, token, account_public_key, timeout=30):
        self.token = token
        self._aes_key = "".join(secrets.choice(_KEY_ALPHABET) for _ in range(16)).encode()
        self._login_rsa = PKCS1_v1_5.new(RSA.import_key(base64.b64decode(_LOGIN_PUBLIC_KEY)))
        self._account_rsa = PKCS1_v1_5.new(RSA.import_key(base64.b64decode(account_public_key)))
        self._ws = create_connection(f"{websocket_url}/{uuid.uuid4().hex}", timeout=timeout)

    def _encrypt(self, text):
        cipher = AES.new(self._aes_key, AES.MODE_CBC, _AES_IV)
        return base64.urlsafe_b64encode(cipher.encrypt(pad(text.encode(), 16))).decode().rstrip("=")

    def _decrypt(self, text):
        raw = base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))
        cipher = AES.new(self._aes_key, AES.MODE_CBC, _AES_IV)
        return unpad(cipher.decrypt(raw), 16).decode()

    def _request_key(self, rsa):
        return base64.b64encode(rsa.encrypt(self._aes_key + b"&" + str(int(time.time())).encode())).decode()

    def _send(self, cmd, data, rsa):
        if cmd not in _ALLOWED_REQUESTS:
            raise ValueError(f"refusing to send command {cmd}: only login and real-data reads are allowed")
        message = {"uuid": str(uuid.uuid4()), "cmd": cmd, "key": self._request_key(rsa),
                   "data": self._encrypt(json.dumps(data)), "lang": "en", "tag": ""}
        self._ws.send(json.dumps(message))

    def login(self):
        self._send(CMD_LOGIN_REQUEST, {"token": self.token}, self._login_rsa)

    def request_real_data(self, addresses):
        """Ask for the current value of each register address (a read; changes nothing)."""
        self._send(CMD_REALDATA_REQUEST, [{"address": a} for a in addresses], self._account_rsa)

    def receive(self):
        """Wait for the next message and return it with its data decrypted."""
        message = json.loads(self._ws.recv())
        data = message.get("data")
        if isinstance(data, str) and data.strip():
            try:
                message["data"] = json.loads(self._decrypt("".join(data.split())))
            except Exception as e:  # keep the raw text so nothing is lost
                message["decrypt_error"] = str(e)
        return message

    def close(self):
        try:
            self._ws.close()
        except Exception:
            pass
