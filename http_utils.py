import logging
import os
import requests
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("http_utils")

def http_post(service_url, payload, headers):
    logger.debug(f"Call POST {service_url}")
    logger.debug(f"Payload {payload}")
    logger.debug(f"headers {headers}")
    try:
        response = requests.post(service_url, headers=headers, json=payload)
        logger.debug(f"Response {response}")
        return response
    except Exception as e:
        logger.error(f"Error sending POST request: {e}")
        return False

def http_get(service_url, headers):
    logger.debug(f"Call GET {service_url}")
    logger.debug(f"headers {headers}")
    try:
        response = requests.get(service_url, headers=headers)
        logger.debug(f"Response {response}")
        return response
    except Exception as e:
        logger.error(f"Error sending GET request: {e}")
        return False