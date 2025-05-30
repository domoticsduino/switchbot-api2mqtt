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
from threading import Thread
from dotenv import load_dotenv

_VERSION = "0.1"

load_dotenv() 
log_file = os.getenv("LOG_FILE", "/logs/switchbot_api2mqtt.log")
# --- Logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),  
        logging.FileHandler(log_file, encoding='utf-8') 
    ]
)
logger = logging.getLogger("switchbot-api2mqtt")

# --- Configurazioni ---
MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_USERNAME = os.getenv("MQTT_USERNAME")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")
MQTT_CLIENT_ID = os.getenv("MQTT_CLIENT_ID", "switchbot_api2mqtt")
MQTT_TOPIC_COMMAND = os.getenv("MQTT_TOPIC_COMMAND", "switchbot/lock/cmd")
MQTT_TOPIC_STATUS = os.getenv("MQTT_TOPIC_STATUS", "switchbot/lock/status")
SWITCHBOT_TOKEN = os.getenv("SWITCHBOT_TOKEN")
SWITCHBOT_SECRET = os.getenv("SWITCHBOT_SECRET")
SWITCHBOT_DEVICE_ID = os.getenv("SWITCHBOT_DEVICE_ID")

# --- Funzione per generare headers autenticati ---
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

# --- Funzioni per SwitchBot ---
def get_lock_status():
    logger.info(f"Get Status")
    url = f"https://api.switch-bot.com/v1.1/devices/{SWITCHBOT_DEVICE_ID}/status"
    headers = generate_headers()
    try:
        response = requests.get(url, headers=headers)
        data = response.json()
        if data.get("message") == "success":
            return data.get("body")
    except Exception as e:
        logger.error(f"Error getting status: {e}")
    return None
    
def get_devices():
    url = f"https://api.switch-bot.com/v1.1/devices"
    headers = generate_headers()
    try:
        response = requests.get(url, headers=headers)
        data = response.json()
        if data.get("message") == "success":
            return data.get("body")
    except Exception as e:
        logger.error(f"Error getting devices: {e}")
    return None

def send_command(command):
    url = f"https://api.switch-bot.com/v1.1/devices/{SWITCHBOT_DEVICE_ID}/commands"
    headers = generate_headers()
    payload = {
        "command": command,
        "parameter": "default",
        "commandType": "command"
    }
    try:
        response = requests.post(url, headers=headers, json=payload)
        logger.info(f"Response {response}")
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Error send command: {e}")
        return False

# --- MQTT Handlers ---
def on_connect(client, userdata, flags, rc, properties=None):
    logger.info(f"MQTT connection successfully")
    client.subscribe(MQTT_TOPIC_COMMAND)

def on_message(client, userdata, msg):
    command = msg.payload.decode().strip().lower()
    logger.info(f"Command {command}")
    if command in ["lock", "unlock"]:
        success = send_command(command)
        if not success:
            logger.error("Error executing command")
    elif command == "devices":
        res = get_devices()
        client.publish(MQTT_TOPIC_STATUS, json.dumps(res))
    elif command == "status":
        res = get_lock_status()
        client.publish(MQTT_TOPIC_STATUS, json.dumps(res))

# --- Thread per aggiornamento stato periodico ---
def poll_status_loop(client):
    while True:
        status = get_lock_status()
        if status:
            client.publish(MQTT_TOPIC_STATUS, json.dumps(status))
        time.sleep(60)  # ogni minuto

# --- Main ---
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
    
    poller = Thread(target=poll_status_loop, args=(mqtt_client,), daemon=True)
    poller.start()
    
    logger.info("Waiting for messages... CTRL+C to exit.")
    try:
        mqtt_client.loop_forever()
    except KeyboardInterrupt:
        logger.error("Subscriber disconnected.")
    finally:
        mqtt_client.disconnect()
        logger.error("Subscriber disconnected.")
