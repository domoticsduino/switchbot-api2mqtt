# switchbot-api2mqtt

This Python script acts as a bridge between **SwitchBot's cloud APIs** (1.1 version) and the **MQTT protocol**.

It allows you to seamlessly integrate your SwitchBot devices, such as smart locks, into your existing smart home ecosystem that supports MQTT, like OpenHAB.

Designed for ease of deployment, this solution can be run natively or as a Docker container, providing a portable and consistent environment.

By translating commands and status updates between SwitchBot's proprietary API and standard MQTT messages, this solution enables you to control and monitor your SwitchBot devices directly from your MQTT-enabled smart home platform. This eliminates the need for separate apps or complex workarounds, providing a unified and efficient control experience.

***Please, use version 0.1 if you would like to control your smart lock pro in a simple way***

## Usage

- Copy *.env-template* in *.env* and populate config variables according to your setup
- Follow this guide to obtain your authentication secrets: https://github.com/OpenWonderLabs/SwitchBotAPI?tab=readme-ov-file#getting-started
- Run switchbot_api2mqtt.py using your python environment OR run with docker compose
- Send GET and POST call to Switchbot API to *MQTT_TOPIC_COMMAND* topic using an MQTT publisher
- Get responses subscribing to *MQTT_TOPIC_RESPONSE* topic
- Actually the *MQTT_TOPIC_STATUS* topic is not used

### Payload template

{"method": "[get/post]", "service": "[path_url]", "payload": ["generic_payload_for_POST_call"]}

## *Version 0.2*
 - Generic version to invoke all switcbot API services using GET and POST method
 - MQTT payload containts all the details related to API call
 - Added *MQTT_TOPIC_RESPONSE* topic is used to obtain the last call response
 - Added *API_BASEURL* configuration property to set the API baseurl
 - Removed the *SWITCHBOT_DEVICE_ID* configuration property
 - No more automatic status retrieving

## *Version 0.1*
 - Initial version to test the Smart Lock.
 - The commands are sent as simple strings in the Mqtt message
 - Valid commands are *lock*, *unlock*, *devices*, *status*.
 - Use *devices* command to obtain a list of your devices and get the DEVICE ID of your SMART LOCK
 - Every 60 seconds device status is automatically sent to *MQTT_TOPIC_STATUS* topic 

## SWITCHBOT API Documentation
https://github.com/OpenWonderLabs/SwitchBotAPI?tab=readme-ov-file

# DISCLAIMER

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.