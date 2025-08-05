# switchbot_api2mqtt.py
import logging
import os
import json
import time
import uuid
import hmac
import hashlib
import base64
import paho.mqtt.client as mqtt
import threading
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from http_utils import http_get, http_post
import logging.config

_VERSION = "1.0 beta"

load_dotenv()
with open('logging.json', 'r') as f:
    config = json.load(f)
    logging.config.dictConfig(config)
logger = logging.getLogger("switchbot-api2mqtt")

SWITCHBOT_POLLING_INTERVAL_SEC_MIN = 60

MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_USERNAME = os.getenv("MQTT_USERNAME")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")
MQTT_CLIENT_ID = os.getenv("MQTT_CLIENT_ID", "switchbot_api2mqtt")
MQTT_SMARTLOCK_BASE_TOPIC = os.getenv("MQTT_SMARTLOCK_BASE_TOPIC", "smarthome/smartlock/")
MQTT_GENERIC_BASE_TOPIC = os.getenv("MQTT_GENERIC_BASE_TOPIC", "switchbot/api/generic/")
SWITCHBOT_TOKEN = os.getenv("SWITCHBOT_TOKEN")
SWITCHBOT_SECRET = os.getenv("SWITCHBOT_SECRET")
API_BASEURL = os.getenv("API_BASEURL", "https://api.switch-bot.com/v1.1/")
HTTP_PORT = os.getenv("HTTP_PORT", 80)
SWITCHBOT_DEVICE_TYPE_SMARTLOCKPRO = os.getenv("SWITCHBOT_DEVICE_TYPE_SMARTLOCK", "WoLockPro")
SWITCHBOT_VALID_DEVICE_ID = json.loads(os.getenv("SWITCHBOT_VALID_DEVICE_ID", '[]'))
SWITCHBOT_SMARTLOCK_VALID_COMMAND = json.loads(os.getenv("SWITCHBOT_SMARTLOCK_VALID_COMMAND", '[]'))
try:
    SWITCHBOT_POLLING_INTERVAL_SEC = int(os.getenv("SWITCHBOT_POLLING_INTERVAL_SEC", 0))
except (ValueError, TypeError):
    logger.warning("Invalid value for SWITCHBOT_POLLING_INTERVAL_SEC. Using default 0.")
    SWITCHBOT_POLLING_INTERVAL_SEC = 0
if SWITCHBOT_POLLING_INTERVAL_SEC > 0 and SWITCHBOT_POLLING_INTERVAL_SEC < SWITCHBOT_POLLING_INTERVAL_SEC_MIN:
    logger.warning(f"Invalid SWITCHBOT_POLLING_INTERVAL_SEC ({SWITCHBOT_POLLING_INTERVAL_SEC}). Settings minimun {SWITCHBOT_POLLING_INTERVAL_SEC_MIN}")
    SWITCHBOT_POLLING_INTERVAL_SEC = SWITCHBOT_POLLING_INTERVAL_SEC_MIN

app = Flask(__name__)
@app.route('/sb', methods=['POST'])

def receive_webhook():
    global mqtt_client
    data = request.get_json()
    logger.info(f"Payload: {data}")
    if not data or data.get("eventType") != "changeReport":
        logger.error("Invalid payload")
        return jsonify({'error': 'Invalid payload'}), 400
    context = data.get("context")
    if not context:
        logger.error("Invalid payload")
        return jsonify({'error': 'Invalid payload'}), 400
    devicetype = context.get("deviceType")
    logger.debug(f"Device type: {devicetype}")
    topic = None
    if is_smartlockpro_webhook(devicetype):
        deviceid = context.get("deviceMac")
        if not deviceid:
            logger.error("Invalid payload")
            return jsonify({'error': 'Invalid payload'}), 400
        logger.debug(f"Device id: {deviceid}")
        if not is_valid_deviceid(deviceid):
            logger.error(f"Invalid device id {deviceid}")
            return jsonify({'error': f'Invalid deviceid {deviceid}'}), 400
        topic = f"{MQTT_SMARTLOCK_BASE_TOPIC}{deviceid}/event"
    else:
        logger.error("Invalid payload")
        return jsonify({'error': 'Invalid payload'}), 400
    if not topic:
        logger.error("Invalid payload")
        return jsonify({'error': 'Invalid payload'}), 400
    
    logger.debug(f"Send message to topic: {topic}")
    mqtt_client.publish(topic, json.dumps(data))
    return jsonify({'status': 'ok'})

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
    
def start_http_server():
    app.run(host='0.0.0.0', port=HTTP_PORT)

def on_connect(client, userdata, flags, rc, properties=None):
    logger.info(f"MQTT connection successfully ({rc})")
    if MQTT_SMARTLOCK_BASE_TOPIC:
        client.subscribe(f"{MQTT_SMARTLOCK_BASE_TOPIC}+/cmnd")
    if MQTT_GENERIC_BASE_TOPIC:
        client.subscribe(f"{MQTT_GENERIC_BASE_TOPIC}cmnd")

def on_message(client, userdata, msg):
    try:
        logger.info(f"topic received: {msg.topic}")
        if is_smartlock_topic(msg.topic):
            logger.debug("It's a smartlock topic")
            deviceid = get_id_from_topic(msg.topic, 3)
            logger.debug(f"Device id: {deviceid}")
            if is_valid_deviceid(deviceid):
                command = msg.payload.decode('utf-8').lower()
                logger.info(f"Payload: {command}")
                if is_smartlockpro_validcommand(command):
                    logger.debug("Valid command")
                    res = None
                    if command == "status":
                        res = http_get(f"{API_BASEURL}devices/{deviceid}/status", generate_headers())
                    else:
                        res = http_post(f"{API_BASEURL}devices/{deviceid}/commands", {"command": command, "commandType": "command"}, generate_headers())
                    if res is not None:
                        logger.debug(f"Response: {res.status_code}")
                        if res.status_code == 200:
                            client.publish(f"{msg.topic[0:-4]}response", json.dumps(res.json()))
                        else:
                            logger.error(f"Invalid response {res}")
                    else:
                        logger.error(f"Generic error")
                else:
                    logger.error("Invalid command")
            else:
                logger.error("Invalid device id")
        elif is_generic_topic(msg.topic):
            logger.debug("It's a generic topic")
            payload = msg.payload.decode('utf-8')
            data = json.loads(payload)
            method = data.get("method")
            service = data.get("service")
            logger.debug(f"method {method}")
            logger.debug(f"service {service}")
            res = None
            if service and method == "get":
                res = http_get(f"{API_BASEURL}{service}", generate_headers())
            elif service and method == "post":
                res = http_post(f"{API_BASEURL}{service}", data.get("payload"), generate_headers())
            else:
                logger.error(f"Invalid payload")
            if res is not None:
                if res.status_code == 200:
                    topic = f"{MQTT_GENERIC_BASE_TOPIC}response"
                    client.publish(topic, json.dumps(res.json()))
                else:
                    logger.error(f"Invalid response {res}")
        else:
             logger.error(f"Invalid topic")
    except Exception as e:
        logger.error(f"Generic error: {e}")

def is_smartlock_topic(topic):
    return topic.startswith(MQTT_SMARTLOCK_BASE_TOPIC)
    
def is_generic_topic(topic):
    return topic.startswith(MQTT_GENERIC_BASE_TOPIC)

def is_smartlockpro_webhook(type):
    return type == SWITCHBOT_DEVICE_TYPE_SMARTLOCKPRO

def is_smartlockpro_validcommand(command):
    return command in SWITCHBOT_SMARTLOCK_VALID_COMMAND
    
def is_valid_deviceid(deviceid):
    return deviceid in SWITCHBOT_VALID_DEVICE_ID
    
def get_id_from_topic(topic, idx):
    segments = topic.split('/')
    if len(segments) >= idx:
        return segments[idx - 1]
    else:
        return None

def print_initial_info():
    logger.info(f"START version {_VERSION}")
    logger.debug(f"MQTT_BROKER: {MQTT_BROKER}")
    logger.debug(f"MQTT_PORT: {MQTT_PORT}")
    logger.debug(f"MQTT_USERNAME: {MQTT_USERNAME}")
    logger.debug(f"MQTT_CLIENT_ID: {MQTT_CLIENT_ID}")
    logger.debug(f"MQTT_SMARTLOCK_BASE_TOPIC: {MQTT_SMARTLOCK_BASE_TOPIC}")
    logger.debug(f"MQTT_GENERIC_BASE_TOPIC: {MQTT_GENERIC_BASE_TOPIC}")
    logger.debug(f"HTTP_PORT: {HTTP_PORT}")
    logger.debug(f"API_BASEURL: {API_BASEURL}")
    logger.debug(f"SWITCHBOT_DEVICE_TYPE_SMARTLOCKPRO: {SWITCHBOT_DEVICE_TYPE_SMARTLOCKPRO}")
    logger.debug(f"SWITCHBOT_VALID_DEVICE_ID: {SWITCHBOT_VALID_DEVICE_ID}")
    logger.debug(f"SWITCHBOT_SMARTLOCK_VALID_COMMAND: {SWITCHBOT_SMARTLOCK_VALID_COMMAND}")
    logger.debug(f"SWITCHBOT_POLLING_INTERVAL_SEC: {SWITCHBOT_POLLING_INTERVAL_SEC}")
    
def poll_status():
    time.sleep(10)
    while True:
        try:
            logger.info("Starting polling status thread")
            for deviceid in SWITCHBOT_VALID_DEVICE_ID:
                topic_cmnd = f"{MQTT_SMARTLOCK_BASE_TOPIC}{deviceid}/cmnd"
                logger.debug(f"Sending 'status' command on topic: {topic_cmnd}")
                mqtt_client.publish(topic_cmnd, "status")
        except Exception as e:
            logger.error(f"Error in polling thread: {e}")
        time.sleep(SWITCHBOT_POLLING_INTERVAL_SEC)

def start_poll_thread():
    poll_thread = threading.Thread(target=poll_status)
    poll_thread.daemon = True
    poll_thread.start()
    
if __name__ == "__main__":
    
    print_initial_info()
    
    # HTTP
    http_thread = threading.Thread(target=start_http_server)
    http_thread.daemon = True
    http_thread.start()
    
    # MQTT
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
    
    if SWITCHBOT_POLLING_INTERVAL_SEC > 0:
        start_poll_thread()
    else:
        logger.warning("Polling status thread disabled!")

    logger.info("Waiting for messages...")
    try:
        mqtt_client.loop_forever()
    except KeyboardInterrupt:
        logger.error("Subscriber disconnected.")
    finally:
        mqtt_client.disconnect()
        logger.error("Subscriber disconnected.")
