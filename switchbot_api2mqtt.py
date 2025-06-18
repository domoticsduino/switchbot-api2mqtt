# switchbot_api2mqtt.py
import logging
import os
import json
import time
import uuid
import hmac
import hashlib
import base64
import requests
import paho.mqtt.client as mqtt
import importlib.metadata
from threading import Thread
from dotenv import load_dotenv

_VERSION = "0.2"

load_dotenv()
log_file = os.getenv("LOG_FILE", "/logs/switchbot_api2mqtt.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_file, encoding='utf-8')
    ]
)
logger = logging.getLogger("switchbot-api2mqtt")

MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_USERNAME = os.getenv("MQTT_USERNAME")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")
MQTT_CLIENT_ID = os.getenv("MQTT_CLIENT_ID", "switchbot_api2mqtt")
MQTT_TOPIC_COMMAND = os.getenv("MQTT_TOPIC_COMMAND", "switchbot/lock/cmd")
MQTT_TOPIC_STATUS = os.getenv("MQTT_TOPIC_STATUS", "switchbot/lock/status")
MQTT_TOPIC_RESPONSE = os.getenv("MQTT_TOPIC_RESPONSE", "switchbot/lock/response")
SWITCHBOT_TOKEN = os.getenv("SWITCHBOT_TOKEN")
SWITCHBOT_SECRET = os.getenv("SWITCHBOT_SECRET")
API_BASEURL = os.getenv("API_BASEURL", "https://api.switch-bot.com/v1.1/")

def generate_headers():
    t = str(int(time.time() * 1000))
    nonce = str(uuid.uuid4())
    string_to_sign = SWITCHBOT_TOKEN + t + nonce
    sign = base64.b64encode(hmac.new(SWITCHBOT_SECRET.encode(), msg=string_to_sign.encode(), digestmod=hashlib.sha256).digest()).decode()

    return {
        "Authorization": SWITCHBOT_TOKEN,
        "sign": sign,
        "t": t,
        "nonce": nonce,
        "Content-Type": "application/json; charset=utf8"
    }

def post(service_url, payload):
    url = f"{API_BASEURL}{service_url}"
    headers = generate_headers()
    logger.info(f"Call POST {url}")
    logger.debug(f"Payload {payload}")
    logger.debug(f"headers {headers}")
    try:
        response = requests.post(url, headers=headers, json=payload)
        logger.debug(f"Response {response}")
        return response
    except Exception as e:
        logger.error(f"Error sending POST request: {e}")
        return False

def get(service_url):
    url = f"{API_BASEURL}{service_url}"
    headers = generate_headers()
    logger.info(f"Call GET {url}")
    logger.debug(f"headers {headers}")
    try:
        response = requests.get(url, headers=headers)
        logger.debug(f"Response {response}")
        return response
    except Exception as e:
        logger.error(f"Error sending GET request: {e}")
        return False

def on_connect(client, userdata, flags, rc, properties=None):
    logger.info(f"MQTT connection successfully ({rc})")
    client.subscribe(MQTT_TOPIC_COMMAND)

def on_message(client, userdata, msg):
    try:
        payload = msg.payload.decode('utf-8')
        data = json.loads(payload)
        method = data.get("method")
        service = data.get("service")
        logger.info(f"method {method}")
        logger.info(f"service {service}")
        res = None
        if service and method == "get":
            res = get(service)
        elif service and method == "post":
            res = post(service, data.get("payload"))
        else:
            logger.error(f"Invalid payload")
        if res is not None:
            if res.status_code == 200:
                client.publish(MQTT_TOPIC_RESPONSE, json.dumps(res.json()))
            else:
                logger.error("Invalid response {res}")
    except json.JSONDecodeError as jsonerror:
        logger.error("Invalid JSON message: {jsonerror}")
    except Exception as e:
        logger.error(f"Generic error: {e}")

if __name__ == "__main__":
    logger.info(f"START version {_VERSION}")
    mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, MQTT_CLIENT_ID)
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    if MQTT_USERNAME and MQTT_PASSWORD:
        mqtt_client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    try:
        mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
    except Exception as e:
        logger.error(f"MQTT Connection error: {e}")
        exit()
    
    logger.info("Waiting for messages...")
    try:
        mqtt_client.loop_forever()
    except KeyboardInterrupt:
        logger.error("Subscriber disconnected.")
    finally:
        mqtt_client.disconnect()
        logger.error("Subscriber disconnected.")
