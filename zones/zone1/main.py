"""
Smart Fire Fighting System - Zone Node Firmware
ESP32 + MicroPython

This node is responsible for ONE zone in the factory.
- Reads flame sensor + temperature sensor
- Reacts locally & instantly (fail-safe, works even if network is down):
    -> activates relay (extinguisher / solenoid)
    -> sounds local buzzer + LED alarm
- Publishes over MQTT (HiveMQ broker):
    -> factory/zoneX/telemetry   (periodic sensor readings)
    -> factory/zoneX/alert       (urgent, sent the instant fire is detected)
- Subscribes to neighboring zones' alert topics:
    -> triggers a DIFFERENT local warning pattern (not full alarm)
       so workers in this zone know a NEARBY zone is on fire.

Wokwi simulation notes:
    - Flame sensor not available in default Wokwi parts -> using a
      potentiometer (ADC) or a pushbutton/slide switch (digital)
    - DS18B20 (temperature, OneWire) IS available in Wokwi.
"""

import machine
import network
import time
import ujson
from umqtt.simple import MQTTClient

# ============================================================
# CONFIGURATION - change per zone / deployment
# ============================================================

ZONE_ID = "zone1"                       # unique id for this zone
NEIGHBOR_ZONES = ["zone-1", "zone2"]     # zones physically adjacent to this one

WIFI_SSID = "Wokwi-GUEST"
WIFI_PASS = ""

MQTT_BROKER = "broker.hivemq.com"        
MQTT_PORT = 1883                        
MQTT_CLIENT_ID = "esp32_" + ZONE_ID

TOPIC_TELEMETRY = "factory/{}/telemetry".format(ZONE_ID)
TOPIC_ALERT = "factory/{}/alert".format(ZONE_ID)
TOPIC_STATUS = "factory/{}/status".format(ZONE_ID)

# thresholds - tune to your sensors
TEMP_THRESHOLD_C = 60.0
NTC_BETA = 3950
NTC_T0_KELVIN = 298.15       # 25C reference temperature
ADC_MAX = 4095.0             # ESP32 ADC is 12-bit (0-4095)


FLAME_DETECTED_VALUE = 1     # for digital flame sensor: 1 = fire,  
TELEMETRY_INTERVAL_S = 5     # how often to publish normal readings

# ============================================================
# PIN SETUP
# ============================================================

FLAME_PIN = 14        # digital input from flame sensor (or pushbutton in Wokwi)
TEMP_ADC_PIN = 34      # analog input if using a simple analog temp sensor (e.g. LM35)
RELAY_PIN = 26        # controls extinguisher / solenoid valve
BUZZER_PIN = 27
LED_ALARM_PIN = 25       # own-zone fire indicator
LED_WARNING_PIN = 33     # neighbor-zone warning indicator

flame_sensor = machine.Pin(FLAME_PIN, machine.Pin.IN, machine.Pin.PULL_UP)
temp_adc = machine.ADC(machine.Pin(TEMP_ADC_PIN))
temp_adc.atten(machine.ADC.ATTN_11DB)   # full 0-3.3V range

relay = machine.Pin(RELAY_PIN, machine.Pin.OUT)
buzzer = machine.Pin(BUZZER_PIN, machine.Pin.OUT)
led_alarm = machine.Pin(LED_ALARM_PIN, machine.Pin.OUT)
led_warning = machine.Pin(LED_WARNING_PIN, machine.Pin.OUT)

relay.value(0)
buzzer.value(0)
led_alarm.value(0)
led_warning.value(0)

# ============================================================
# STATE
# ============================================================

fire_active = False
mqtt = None
last_telemetry_time = 0

# ============================================================
# WIFI + MQTT SETUP
# ============================================================

def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        print("Connecting to WiFi...")
        wlan.connect(WIFI_SSID, WIFI_PASS)
        timeout = 15
        while not wlan.isconnected() and timeout > 0:
            time.sleep(1)
            timeout -= 1
    if wlan.isconnected():
        print("WiFi connected:", wlan.ifconfig())
        return True
    print("WiFi connection FAILED - continuing in local-only mode")
    return False


def mqtt_message_callback(topic, msg):
    topic = topic.decode()
    data = ujson.loads(msg)

    for zone in NEIGHBOR_ZONES:
        if topic == "factory/{}/alert".format(zone):

            if data.get("event") == "fire_detected":
                handle_neighbor_alert(zone)

            elif data.get("event") == "fire_cleared":
                handle_neighbor_clear()


def connect_mqtt():
    global mqtt
    try:
        client = MQTTClient(MQTT_CLIENT_ID, MQTT_BROKER, port=MQTT_PORT, keepalive=30)
        client.set_callback(mqtt_message_callback)
        client.connect()
        for zone in NEIGHBOR_ZONES:
            client.subscribe("factory/{}/alert".format(zone))
        print("MQTT connected and subscribed to neighbor alerts")
        mqtt = client
        return True
    except Exception as e:
        print("MQTT connection failed:", e)
        mqtt = None
        return False


def mqtt_publish(topic, payload_dict):
    """Safe publish - never blocks the local fire-suppression logic."""
    global mqtt
    if mqtt is None:
        return False
    try:
        mqtt.publish(topic, ujson.dumps(payload_dict))
        return True
    except Exception as e:
        print("MQTT publish failed:", e)
        mqtt = None
        return False

# ============================================================
# SENSOR READING
# ============================================================

def read_flame():
    return flame_sensor.value() == FLAME_DETECTED_VALUE


def read_temperature_c():
    import math

    analog_value = temp_adc.read()

    if analog_value <= 0 or analog_value >= ADC_MAX:
        return -273.15  # invalid reading sentinel

    temp_kelvin = 1 / (
        (math.log(1 / (ADC_MAX / analog_value - 1)) / NTC_BETA) + (1 / NTC_T0_KELVIN)
    )
    temp_c = temp_kelvin - 273.15
    return round(temp_c)

# ============================================================
# LOCAL FIRE RESPONSE (fail-safe, no network dependency)
# ============================================================

def activate_local_response():
    """This MUST work even with zero network connectivity."""
    relay.value(1)      # open extinguisher / solenoid
    buzzer.value(1)
    led_alarm.value(1)
    print("!!! LOCAL FIRE RESPONSE ACTIVATED in", ZONE_ID)


def deactivate_local_response():
    relay.value(0)
    buzzer.value(0)
    led_alarm.value(0)


def handle_neighbor_alert(zone):
    """Different pattern than own-zone alarm: a distinct warning, not full response."""
    print("Warning: neighboring", zone, "reported fire")
    led_warning.value(1)

def handle_neighbor_clear():
    led_warning.value(0)


# ============================================================
# MAIN LOGIC
# ============================================================

def check_and_react():
    global fire_active

    flame = read_flame()
    temp = read_temperature_c()

    fire_condition = flame or (temp >= TEMP_THRESHOLD_C)

    if fire_condition and not fire_active:
        fire_active = True
        activate_local_response()   # instant, local, no network needed
        mqtt_publish(TOPIC_ALERT, {
            "zone": ZONE_ID,
            "event": "fire_detected",
            "flame": flame,
            "temperature": temp,
            "timestamp": time.time()
        })

    elif not fire_condition and fire_active:
        # fire cleared - adjust this to your real logic (may need manual reset instead)
        fire_active = False
        deactivate_local_response()
        mqtt_publish(TOPIC_ALERT, {
            "zone": ZONE_ID,
            "event": "fire_cleared",
            "timestamp": time.time()
        })

    return flame, temp


def publish_telemetry(flame, temp):
    mqtt_publish(TOPIC_TELEMETRY, {
        "zone": ZONE_ID,
        "flame": flame,
        "temperature": temp,
        "fire_active": fire_active,
        "timestamp": time.time()
    })
 

def main():
    global last_telemetry_time

    connect_wifi()
    connect_mqtt()

    while True:
        try:
            flame, temp = check_and_react()

            now = time.time()
            if now - last_telemetry_time >= TELEMETRY_INTERVAL_S:
                publish_telemetry(flame, temp)
                last_telemetry_time = now

            if mqtt is not None:
                mqtt.check_msg()   # non-blocking check for neighbor alerts
            else:
                connect_mqtt()     # try to recover connection

            time.sleep(0.5)

        except Exception as e:
            print("Main loop error:", e)
            time.sleep(1)


if __name__ == "__main__":
    main()
