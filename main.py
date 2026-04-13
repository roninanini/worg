"""
Copyright (C) 2025, Roni Araujo Nanini

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.

You can access the source code on site: https://github.com/roninanini/worg
"""

import network
from time import sleep
import time
from variables import IO
from Libs.umqtt_simple import MQTTClient
from Libs.ds3231 import DS3231
from machine import I2C, Pin, ADC
import Libs.mcp23017
from Libs.soil import sensor_soil
import passwords

# -----------ATRIBUTES-----------#
io = IO()

SSID = passwords.SSID
PASSWORD = passwords.PASSWORD
MQTT_ID = passwords.MQTT_ID
MQTT_SERVER = passwords.MQTT_SERVER
MQTT_PORT = passwords.MQTT_PORT
MQTT_USER = passwords.MQTT_USER
MQTT_PASSWORD = passwords.MQTT_PASSWORD

i2c = I2C(0, scl=Pin(22), sda=Pin(21), freq=400000)
mcp = Libs.mcp23017.MCP23017(i2c, 0x27)
ds = DS3231(i2c)
circle = 10 * 60


# -----------INTERNET CONECTION ----------#
def setup_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    print("[STATUS]: Connecting to WiFi...")
    print(f"SSID: {SSID}")

    if not wlan.isconnected():
        wlan.connect(SSID, PASSWORD)
        print("[STATUS]: Trying connection...")
        timeout = 15
        start_time = time.time()

        while not wlan.isconnected() and (time.time() - start_time) < timeout:
            print(".", end="")
            sleep(1)
        print()

        if wlan.isconnected():
            print(f"[OK]: WiFi connected!")
            print(f"IP: {wlan.ifconfig()[0]}")
            print(f"Signal: {wlan.status('rssi')} dBm")
        else:
            print(f"[ERROR]: WiFi failed!")

    return wlan


# -----------SETTING PARAMETER OF LIGHT AND ENVIRONMENT ----------#
def write_data(topic, message):
    topic = topic.decode('utf-8')
    value = message.decode('utf-8')
    plant_phase = read_data()
    if topic == 'worg/plant_phase':
        plant_phase = value

    with open('data.csv', 'w') as f:
        f.write(f'{plant_phase}')


def read_data():
    try:
        with open('data.csv', 'r') as f:
            line = f.read()
            return line.strip()
    except Exception as e:
        return "0"


# SETTING CONDITIONS TO CONTROL
def water_plant(soil_moisture, state, water_pump, plant_name=""):
    """Water a plant based on soil moisture and state"""
    if soil_moisture < 10:
        print(f"[CONTROL]: Watering {plant_name} - State: {state}. Waiting...")
        # Determine watering cycles based on state
        if state == 0:
            cycles = 0
        elif state == 1:
            cycles = 3
        elif state == 2:
            cycles = 6
        elif state == 3:
            cycles = 12
        else:
            cycles = 0
        total_cycles = cycles
        # Execute watering cycles
        while cycles > 0:
            print(f"Cycle {cycles} of {total_cycles}")
            water_pump(1)  # Turn pump ON
            sleep(10)  # Water for 10 seconds
            water_pump(0)  # Turn pump OFF
            sleep(10)  # Pause for 10 seconds
            cycles -= 1  # Decrement counter

wlan = setup_wifi()
client_mqtt = None

if wlan.isconnected():
    try:
        client_mqtt = MQTTClient(MQTT_ID, server=MQTT_SERVER, port=MQTT_PORT, user=MQTT_USER, password=MQTT_PASSWORD, keepalive=300)
        client_mqtt.set_callback(write_data)
        client_mqtt.connect()
        client_mqtt.subscribe('worg/plant_phase', qos=1)
        print("[OK]: MQTT connected")
    except Exception as e:
        print(f"[ERROR]: MQTT connection failed: {e}")
        client_mqtt = None
else:
    print("[ERROR]: Cannot connect MQTT - WiFi not connected")

sleep(10)

while True:
    if not wlan.isconnected():
        print("[ERROR]: WiFi disconnected, reconnecting...")
        wlan = setup_wifi()

        if wlan.isconnected():
            try:
                if client_mqtt is None:
                    client_mqtt = MQTTClient(MQTT_ID, server=MQTT_SERVER, port=MQTT_PORT, user=MQTT_USER,
                                             password=MQTT_PASSWORD, keepalive=300)
                    client_mqtt.set_callback(write_data)
                client_mqtt.connect()
                client_mqtt.subscribe('worg/plant_phase', qos=1)
                print("[OK]: MQTT reconnected")
            except Exception as e:
                print(f"[ERROR]: MQTT reconnect failed: {e}")
                client_mqtt = None
        else:
            sleep(5)
            continue

    if wlan.isconnected() and client_mqtt is not None:
        try:
            try:
                temp = io.temp()
                humid = io.humid()
                pressure = io.pressure()
                vpd = io.vpd()
                print("[OK]: Getting data from sensor BME280")
            except Exception as e:
                temp = 25
                humid = 60
                pressure = 950
                vpd = 1
                print("[ERROR]: Getting data from sensor BME280")
            try:
                voltage = io.voltage()
                current_val = io.current()
                active_power = io.active_power()
                active_energy = io.active_energy()
                frequency = io.frequency()
                power_factor = io.power_factor()
                print("[OK]: Getting data from module PZEM")
            except Exception as e:
                voltage = 120
                current_val = 2
                active_power = 1
                active_energy = 1
                frequency = 60
                power_factor = 1
                print("[ERROR]: Getting data from module PZEM")

            # SOIL SENSORS
            try:
                soil_1 = str(io.soil_1())
                print("[OK]: Getting data from Soil 1")
            except Exception as e:
                soil_1 = '4095'
                print("[ERROR]: Getting data from Soil 1")
            try:
                soil_2 = str(io.soil_2())
                print("[OK]: Getting data from Soil 2")
            except Exception as e:
                soil_2 = '4095'
                print("[ERROR]: Getting data from Soil 2")
            try:
                soil_3 = str(io.soil_3())
                print("[OK]: Getting data from Soil 3")
            except Exception as e:
                soil_3 = '4095'
                print("[ERROR]: Getting data from Soil 3")
            try:
                soil_4 = str(io.soil_4())
                print("[OK]: Gettinf data from Soil 4")
            except Exception as e:
                soil_4 = '4095'
                print("[ERROR]: Getting data from Soil 4")

            # -----------POINTS OF WEATHER TO GRAFANA -----------#
            client_mqtt.publish('worg/weather/temp', f'{{"temperature": {temp}}}', retain=False, qos=1)
            client_mqtt.publish('worg/weather/humid', f'{{"humidity": {humid}}}', retain=False, qos=1)
            client_mqtt.publish('worg/weather/pressure', f'{{"pressure": {pressure}}}', retain=False, qos=1)
            client_mqtt.publish('worg/weather/vpd', f'{{"Vapour-pressure deficit": {vpd}}}', retain=False, qos=1)
            print("[OK]: MQTT temperature")

            # -----------ELECTRICAL POINTS TO GRAFANA -----------#
            client_mqtt.publish('worg/electrical/voltage', f'{{"voltage": {voltage}}}', retain=False, qos=1)
            client_mqtt.publish('worg/electrical/current', f'{{"current": {current_val}}}', retain=False, qos=1)
            client_mqtt.publish('worg/electrical/active_power', f'{{"active power": {active_power}}}', retain=False,
                                qos=1)
            client_mqtt.publish('worg/electrical/active_energy', f'{{"active energy": {active_energy}}}', retain=False,
                                qos=1)
            client_mqtt.publish('worg/electrical/frequency', f'{{"frequency": {frequency}}}', retain=False, qos=1)
            client_mqtt.publish('worg/electrical/power_factor', f'{{"power factor": {power_factor}}}', retain=False,
                                qos=1)
            print("[OK]: MQTT Modbus")

            # -----------POINTS OF SOIL TO GRAFANA -----------#
            client_mqtt.publish('worg/soil1', f'{{"soil_moisture 1": {soil_1}}}', retain=False, qos=1)
            client_mqtt.publish('worg/soil2', f'{{"soil_moisture 2": {soil_2}}}', retain=False, qos=1)
            client_mqtt.publish('worg/soil3', f'{{"soil_moisture 3": {soil_3}}}', retain=False, qos=1)
            client_mqtt.publish('worg/soil4', f'{{"soil_moisture 4": {soil_4}}}', retain=False, qos=1)
            print('[OK]: MQTT Soil')
        except Exception as e:
            try:
                client_mqtt.disconnect()
                print("[OK]: MQTT Disconnect")
            except:
                pass
                print("[ERROR]: Disconnect failed")

    try:
        # CONTROL
        if io.temp() < 18:
            # Too cold
            io.fan_1(0)
            io.fan_2(0)
            print("[CONTROL]: FAN 1:OFF, FAN 2:OFF")
            if client_mqtt is not None:
                try:
                    client_mqtt.publish('worg/status/fan_1', f'{{"Fan 01": 0}}', retain=True, qos=1)
                    client_mqtt.publish('worg/status/fan_2', f'{{"Fan 02": 0}}', retain=True, qos=1)
                    print("[OK]: MQTT -- FAN 1:OFF, FAN 2:OFF")
                except Exception as e:
                    print("[ERROR]: MQTT -- FAN 1:OFF, FAN 2:OFF")
        elif 18 <= io.temp() < 22:
            # Slightly warm - minimal cooling
            io.fan_1(1)
            io.fan_2(0)
            print("[CONTROL]: FAN 1:ON, FAN 2:OFF")
            if client_mqtt is not None:
                try:
                    client_mqtt.publish('worg/status/fan_1', f'{{"Fan 01": 1}}', retain=True, qos=1)
                    client_mqtt.publish('worg/status/fan_2', f'{{"Fan 02": 0}}', retain=True, qos=1)
                    print("[OK]: MQTT -- FAN 1:ON, FAN 2:OFF")
                except Exception as e:
                    print("[ERROR]: MQTT -- FAN 1:ON, FAN 2:OFF")
        elif 22 <= io.temp() < 25:
            # Moderately warm - more cooling
            io.fan_1(1)
            io.fan_2(1)
            print("[CONTROL]: FAN 1:ON, FAN 2:ON")
            if client_mqtt is not None:
                try:
                    client_mqtt.publish('worg/status/fan_1', f'{{"Fan 01": 1}}', retain=True, qos=1)
                    client_mqtt.publish('worg/status/fan_2', f'{{"Fan 02": 1}}', retain=True, qos=1)
                    print("[OK]: MQTT -- FAN 1:ON, FAN 2:ON")
                except Exception as e:
                    print("[ERROR]: MQTT -- FAN 1:ON, FAN 2:ON")
        else:
            # Too hot - maximum cooling
            io.fan_1(1)
            io.fan_2(1)
            print("[CONTROL]: FAN 1:ON, FAN 2:ON")
            if client_mqtt is not None:
                try:
                    client_mqtt.publish('worg/status/fan_1', f'{{"Fan 01": 1}}', retain=True, qos=1)
                    client_mqtt.publish('worg/status/fan_2', f'{{"Fan 02": 1}}', retain=True, qos=1)
                    print("[OK]: MQTT -- FAN 1:ON, FAN 2:ON")
                except Exception as e:
                    print("[ERROR]: MQTT -- FAN 1:ON, FAN 2:ON")

        states = read_data()
        print(f"[STATUS]: Plant phase: {states[0]}")
        if int(states[0]) == 1:
            vpd_min = 0.5
            vpd_max = 0.7
            hour_min = 10
            hour_max = 16
        elif int(states[0]) == 2:
            vpd_min = 0.7
            vpd_max = 1
            hour_min = 10
            hour_max = 16
        elif int(states[0]) == 3:
            vpd_min = 1
            vpd_max = 1.3
            hour_min = 7
            hour_max = 19
        else:
            vpd_min = 0.8
            vpd_max = 1.2
            hour_min = 10
            hour_max = 16

        if io.vpd() < vpd_min:
            io.deshumidifier(1)
            io.humidifier(0)
            print("[CONTROL]: HUM:OFF, DESHUM:ON")
            if client_mqtt is not None:
                try:
                    client_mqtt.publish('worg/status/deshumidifier', f'{{"Deshumidifier": 1}}', retain=True, qos=1)
                    client_mqtt.publish('worg/status/humidifier', f'{{"Humidifier": 0}}', retain=True, qos=1)
                    print("[OK]: MQTT -- HUM:OFF, DESHUM:ON")
                except Exception as e:
                    print("[ERROR]: MQTT -- HUM:OFF, DESHUM:ON")
        elif vpd_min <= io.vpd() < vpd_max:
            io.deshumidifier(0)
            io.humidifier(0)
            print("[CONTROL]: HUM:OFF, DESHUM:OFF")
            if client_mqtt is not None:
                try:
                    client_mqtt.publish('worg/status/deshumidifier', f'{{"Deshumidifier": 0}}', retain=True, qos=1)
                    client_mqtt.publish('worg/status/humidifier', f'{{"Humidifier": 0}}', retain=True, qos=1)
                    print("[OK]: MQTT -- HUM:OFF, DESHUM:OFF")
                except Exception as e:
                    print("[ERROR]: MQTT -- HUM:OFF, DESHUM:ON")
        else:
            io.deshumidifier(0)
            io.humidifier(1)
            print("[CONTROL]: HUM:ON, DESHUM:OFF")
            if client_mqtt is not None:
                try:
                    client_mqtt.publish('worg/status/deshumidifier', f'{{"Deshumidifier": 0}}', retain=True, qos=1)
                    client_mqtt.publish('worg/status/humidifier', f'{{"Humidifier": 1}}', retain=True, qos=1)
                    print("[OK]: MQTT -- HUM:ON, DESHUM:OFF")
                except Exception as e:
                    print("[ERROR]: MQTT -- HUM:ON, DESHUM:ON")

        # Light control
        HOUR = ds.hour()
        if hour_min <= HOUR < hour_max:
            io.lighting(0)
            print("[CONTROL]: Lightning: OFF")
            if client_mqtt is not None:
                try:
                    client_mqtt.publish('worg/status/lighting', f'{{"Lighting": 0}}', retain=True, qos=1)
                    print("[OK]: MQTT -- Lightning: OFF")
                except Exception as e:
                    print("[ERROR]: MQTT -- Lightning: OFF")
        else:
            io.lighting(1)
            print("[CONTROL]: Lightning: ON")
            if client_mqtt is not None:
                try:
                    client_mqtt.publish('worg/status/lighting', f'{{"Lighting": 1}}', retain=True, qos=1)
                    print("[OK]: MQTT -- Lightning: ON")
                except Exception as e:
                    print("[ERROR]: MQTT -- Lightning: ON")

        # CONTROLLING PLANTS WATERING
        states = read_data()
        water_plant(io.soil_1(), int(states[0]), io.water_pump_1, "Plant 1")
        if client_mqtt is not None:
            try:
                client_mqtt.publish('worg/status/water_pump1', f'{{"Water Pump 01": {"1" if mcp.pin(3) else "0"}}}',
                                    retain=True, qos=1)
                print("[OK]: MQTT -- Water Pump 01: ON")
            except Exception as e:
                print("[ERROR]: MQTT -- Water Pump 01: ON")
        water_plant(io.soil_2(), int(states[0]), io.water_pump_2, "Plant 2")
        if client_mqtt is not None:
            try:
                client_mqtt.publish('worg/status/water_pump2', f'{{"Water Pump 02": {"1" if mcp.pin(2) else "0"}}}',
                                    retain=True, qos=1)
                print("[OK]: MQTT -- Water Pump 02: ON")
            except Exception as e:
                print("[ERROR]: MQTT -- Water Pump 02: ON")
        water_plant(io.soil_3(), int(states[0]), io.water_pump_3, "Plant 3")
        if client_mqtt is not None:
            try:
                client_mqtt.publish('worg/status/water_pump3', f'{{"Water Pump 03": {"1" if mcp.pin(1) else "0"}}}',
                                    retain=True, qos=1)
                print("[OK]: MQTT -- Water Pump 03: ON")
            except Exception as e:
                print("[ERROR]: MQTT -- Water Pump 03: ON")

        water_plant(io.soil_4(), int(states[0]), io.water_pump_4, "Plant 4")
        if client_mqtt is not None:
            try:
                client_mqtt.publish('worg/status/water_pump4', f'{{"Water Pump 04": {"1" if mcp.pin(0) else "0"}}}',
                                    retain=True, qos=1)
                print("[OK]: MQTT -- Water Pump 04: ON")
            except Exception as e:
                print("[ERROR]: MQTT -- Water Pump 04: ON")

        print("Soil: ", sensor_soil.AVERAGE_PLANT1, sensor_soil.AVERAGE_PLANT2, sensor_soil.AVERAGE_PLANT3,
              sensor_soil.AVERAGE_PLANT4)

    except Exception as e:
        pass

    sleep(circle)