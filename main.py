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
v0.0
"""

# ┌─────────────────────────────────────────────────────────────┐
# │                    MQTT COMMANDS                            │
# ├─────────────────────────────────────────────────────────────┤
# │                                                             │
# │  GLOBAL (Lighting + VPD)                                    │
# │  └── plant_phase = 0,1,2,3                                  │
# │                                                             │
# │  WATERING AMOUNT (quantity of water)                        │
# │  ├── worg/watering/plant1 = 0,1,2,3                         │
# │  ├── worg/watering/plant2 = 0,1,2,3                         │
# │  ├── worg/watering/plant3 = 0,1,2,3                         │
# │  └── worg/watering/plant4 = 0,1,2,3                         │
# │                                                             │
# │  WATERING TRIGGER (user sends 1, system resets to 0)        │
# │  ├── worg/watering/trigger/plant1 = 1 (start) / 0 (done)    │
# │  ├── worg/watering/trigger/plant2 = 1 (start) / 0 (done)    │
# │  ├── worg/watering/trigger/plant3 = 1 (start) / 0 (done)    │
# │  └── worg/watering/trigger/plant4 = 1 (start) / 0 (done)    │
# │                                                             │
# │  WATERING ERROR (published by system)                       │
# │  ├── worg/watering/error/plant1 = {"error": 1}              │
# │  ├── worg/watering/error/plant2 = {"error": 1}              │
# │  ├── worg/watering/error/plant3 = {"error": 1}              │
# │  └── worg/watering/error/plant4 = {"error": 1}              │
# │                                                             │
# └─────────────────────────────────────────────────────────────┘

import network
from time import sleep
import time
from variables import IO
from Libs.umqtt_simple import MQTTClient
from Libs.ds3231 import DS3231
from machine import I2C, Pin, ADC
import Libs.mcp23017
import passwords

# -----------ATTRIBUTES-----------#
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

# -----------GLOBAL VARIABLES (Lighting and VPD)-----------#
plant_global_phase = 0

vpd_min = 0.8
vpd_max = 1.2
hour_min = 10
hour_max = 16

# -----------INDIVIDUAL VARIABLES (Watering per plant)-----------#
# Each plant has:
#   phase: water amount (0,1,2,3) - MQTT worg/watering/plantX
#   command: pending watering command (1 = pending, 0 = none)
#   executed: already watered flag (1 = already watered, 0 = not watered)
plants_watering = {
    1: {"phase": 0, "command": 0, "executed": 0},
    2: {"phase": 0, "command": 0, "executed": 0},
    3: {"phase": 0, "command": 0, "executed": 0},
    4: {"phase": 0, "command": 0, "executed": 0},
}

# Flag to avoid watering multiple plants at the same time
is_watering = False

# Variable to store commands received during the MQTT cycle
received_commands = []


# -----------FUNCTIONS TO UPDATE GLOBAL PARAMETERS-----------#
def update_global_parameters():
    global vpd_min, vpd_max, hour_min, hour_max

    if plant_global_phase == 1:
        vpd_min = 0.5
        vpd_max = 0.7
        hour_min = 10
        hour_max = 16
    elif plant_global_phase == 2:
        vpd_min = 0.7
        vpd_max = 1.0
        hour_min = 10
        hour_max = 16
    elif plant_global_phase == 3:
        vpd_min = 1.0
        vpd_max = 1.3
        hour_min = 7
        hour_max = 19
    else:
        vpd_min = 0.8
        vpd_max = 1.2
        hour_min = 10
        hour_max = 16

    print(f"[STATUS]: Parameters updated - Phase: {plant_global_phase}")
    print(f"[STATUS]: Lighting: {hour_min}h to {hour_max}h")
    print(f"[STATUS]: VPD: {vpd_min} to {vpd_max}")


# -----------FUNCTIONS TO SAVE AND LOAD PLANT WATERING DATA-----------#
def save_watering_data():
    try:
        with open('plants_watering.csv', 'w') as f:
            for plant_id in range(1, 5):
                phase = plants_watering[plant_id]["phase"]
                command = plants_watering[plant_id]["command"]
                executed = plants_watering[plant_id]["executed"]
                f.write(f"{plant_id},{phase},{command},{executed}\n")
        print("[OK]: Watering data saved")
    except Exception as e:
        print(f"[ERROR]: Failed to save watering data: {e}")

def load_watering_data():
    global plants_watering
    try:
        with open('plants_watering.csv', 'r') as f:
            lines = f.readlines()
            for line in lines:
                line = line.strip()
                if line:
                    parts = line.split(',')
                    if len(parts) == 4:
                        plant_id = int(parts[0])
                        phase = int(parts[1])
                        command = int(parts[2])
                        executed = int(parts[3])
                        if plant_id in plants_watering:
                            plants_watering[plant_id]["phase"] = phase
                            plants_watering[plant_id]["command"] = command
                            plants_watering[plant_id]["executed"] = executed
        print("[OK]: Watering data loaded")
        print(f"[DEBUG]: plants_watering loaded = {plants_watering}")
    except Exception as e:
        print(f"[STATUS]: No watering data previously saved, using default values")

def save_global_phase():
    try:
        with open('global_phase.csv', 'w') as f:
            f.write(str(plant_global_phase))
        print("[OK]: Global phase saved")
    except Exception as e:
        print(f"[ERROR]: Failed to save global phase: {e}")

def load_global_phase():
    global plant_global_phase
    try:
        with open('global_phase.csv', 'r') as f:
            plant_global_phase = int(f.read().strip())
            if plant_global_phase < 0 or plant_global_phase > 3:
                plant_global_phase = 0
        print(f"[OK]: Global phase loaded: {plant_global_phase}")
        update_global_parameters()
    except Exception as e:
        print(f"[STATUS]: No global phase saved, using default (0)")


# -----------WATERING EXECUTION FUNCTIONS-----------#
def reset_all_pumps():
    """Desliga todas as bombas (protecao no boot)"""
    io.water_pump_1(0)
    io.water_pump_2(0)
    io.water_pump_3(0)
    io.water_pump_4(0)
    print("[PROTECTION]: All pumps turned off")

def publish_watering_error(plant_id):
    """Publica mensagem de erro via MQTT"""
    client = None
    try:
        if wlan.isconnected():
            client = MQTTClient(MQTT_ID, server=MQTT_SERVER, port=MQTT_PORT,
                               user=MQTT_USER, password=MQTT_PASSWORD, keepalive=60)
            client.connect()
            client.publish(f'worg/watering/error/plant{plant_id}', '{"error": 1}', retain=True, qos=1)
            client.disconnect()
            print(f"[MQTT]: Error published for plant {plant_id}")
    except Exception as e:
        print(f"[ERROR]: Failed to publish error for plant {plant_id}: {e}")

def publish_watering_status(plant_id, status):
    """Publica o status da rega (0 = idle/finished, 1 = pending/running)"""
    client = None
    try:
        if wlan.isconnected():
            client = MQTTClient(MQTT_ID, server=MQTT_SERVER, port=MQTT_PORT,
                               user=MQTT_USER, password=MQTT_PASSWORD, keepalive=60)
            client.connect()
            client.publish(f'worg/watering/trigger/plant{plant_id}', str(status), retain=True, qos=1)
            client.disconnect()
            print(f"[MQTT]: Status for plant {plant_id} published: {status}")
    except Exception as e:
        print(f"[ERROR]: Failed to publish status for plant {plant_id}: {e}")

def execute_watering_cycle(plant_id, cycles, water_pump):
    """Executa os ciclos de rega para uma planta com protecao contra interrupcao"""
    global is_watering

    is_watering = True
    error_occurred = False

    try:
        total_cycles = cycles
        while cycles > 0 and not error_occurred:
            print(f"[CONTROL]: Plant {plant_id} - Cycle {cycles} of {total_cycles}")
            water_pump(1)

            # Aguarda com verificacao de erro (simplificada)
            for _ in range(10):
                sleep(1)

            water_pump(0)
            if cycles > 1:
                for _ in range(10):
                    sleep(1)
            cycles -= 1

        if not error_occurred:
            print(f"[CONTROL]: Plant {plant_id} - Watering completed")

    except Exception as e:
        error_occurred = True
        print(f"[ERROR]: Plant {plant_id} - Watering interrupted: {e}")
        water_pump(0)  # Garante bomba desligada
        publish_watering_error(plant_id)

    finally:
        is_watering = False
        return not error_occurred

def water_plant(plant_id):
    """Rega a planta baseado na phase armazenada"""
    state = plants_watering[plant_id]["phase"]
    print(f"[CONTROL]: Watering plant {plant_id} - Amount: {state}")

    if state == 0:
        cycles = 0
    elif state == 1:
        cycles = 4
    elif state == 2:
        cycles = 8
    elif state == 3:
        cycles = 22
    else:
        cycles = 0

    if cycles > 0:
        if plant_id == 1:
            success = execute_watering_cycle(plant_id, cycles, io.water_pump_1)
        elif plant_id == 2:
            success = execute_watering_cycle(plant_id, cycles, io.water_pump_2)
        elif plant_id == 3:
            success = execute_watering_cycle(plant_id, cycles, io.water_pump_3)
        elif plant_id == 4:
            success = execute_watering_cycle(plant_id, cycles, io.water_pump_4)

        if success:
            plants_watering[plant_id]["command"] = 0
            plants_watering[plant_id]["executed"] = 1
            publish_watering_status(plant_id, 0)
            save_watering_data()
            print(f"[CONTROL]: Plant {plant_id} - Watering successful")
        else:
            print(f"[CONTROL]: Plant {plant_id} - Watering failed, error published")
    else:
        print(f"[CONTROL]: Plant {plant_id} - Phase 0, nothing to do")
        plants_watering[plant_id]["command"] = 0
        plants_watering[plant_id]["executed"] = 1
        publish_watering_status(plant_id, 0)
        save_watering_data()

def check_pending_watering():
    """Verifica e executa comandos de rega pendentes (sequencial)"""
    global is_watering

    if is_watering:
        return

    for plant_id in range(1, 5):
        if plants_watering[plant_id]["command"] == 1 and plants_watering[plant_id]["executed"] == 0:
            print(f"[CONTROL]: Executing pending watering for plant {plant_id}")
            publish_watering_status(plant_id, 1)
            water_plant(plant_id)
            sleep(30)


# -----------INTERNET CONNECTION-----------#
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
            print(f"[OK]: IP: {wlan.ifconfig()[0]}")
            print(f"[OK]: Signal: {wlan.status('rssi')} dBm")
        else:
            print(f"[ERROR]: WiFi failed!")

    return wlan


# -----------MQTT CALLBACK-----------#
def write_data(topic, message):
    topic = topic.decode('utf-8')
    value = message.decode('utf-8')
    received_commands.append((topic, value))
    print(f"[MQTT]: Command received - Topic: {topic}, Value: {value}")


# -----------PROCESS RECEIVED COMMANDS-----------#
def process_mqtt_commands():
    global plant_global_phase

    for topic, value in received_commands:
        # Global Phase
        if topic == 'plant_phase':
            try:
                new_phase = int(value)
                if 0 <= new_phase <= 3:
                    plant_global_phase = new_phase
                    update_global_parameters()
                    save_global_phase()
                    print(f"[MQTT]: Global phase changed to {new_phase}")
                else:
                    print(f"[ERROR]: Invalid phase: {new_phase}. Use 0-3")
            except Exception as e:
                print(f"[ERROR]: Error processing global phase: {e}")

        # Watering amount - worg/watering/plantX
        elif topic.startswith('worg/watering/') and not topic.startswith('worg/watering/trigger/') and not topic.startswith('worg/watering/error/'):
            try:
                plant_id = int(topic.split('/')[-1].replace('plant', ''))
                new_phase = int(value)
                if 0 <= new_phase <= 3:
                    if plant_id in plants_watering:
                        plants_watering[plant_id]["phase"] = new_phase
                        print(f"[MQTT]: Plant {plant_id} - Watering amount changed to {new_phase}")
                        save_watering_data()
                else:
                    print(f"[ERROR]: Invalid phase: {new_phase}. Use 0-3")
            except Exception as e:
                print(f"[ERROR]: Error processing watering amount: {e}")

        # Watering trigger - worg/watering/trigger/plantX
        elif topic.startswith('worg/watering/trigger/'):
            try:
                plant_id = int(topic.split('/')[-1].replace('plant', ''))
                trigger = int(value)
                if trigger == 1:
                    if plants_watering[plant_id]["executed"] == 0:
                        plants_watering[plant_id]["command"] = 1
                        save_watering_data()
                        print(f"[MQTT]: Plant {plant_id} - Watering command saved (pending)")
                    else:
                        print(f"[MQTT]: Plant {plant_id} - Already watered, ignoring command")
                else:
                    print(f"[MQTT]: Plant {plant_id} - Invalid trigger value: {trigger}")
            except Exception as e:
                print(f"[ERROR]: Error processing watering trigger: {e}")

    received_commands.clear()


# -----------MQTT CYCLE-----------#
def mqtt_cycle():
    client = None

    try:
        if not wlan.isconnected():
            print("[ERROR]: WiFi not connected, skipping MQTT")
            return

        client = MQTTClient(MQTT_ID, server=MQTT_SERVER, port=MQTT_PORT,
                           user=MQTT_USER, password=MQTT_PASSWORD, keepalive=60)
        client.set_callback(write_data)
        client.connect()
        print("[OK]: MQTT connected")

        # Subscribe to topics
        client.subscribe('plant_phase', qos=1)
        for plant_id in range(1, 5):
            client.subscribe(f'worg/watering/plant{plant_id}', qos=1)
            client.subscribe(f'worg/watering/trigger/plant{plant_id}', qos=1)

        print("[MQTT]: Waiting for commands...")
        start_wait = time.time()
        while time.time() - start_wait < 2:
            client.check_msg()
            sleep(0.1)

        process_mqtt_commands()

        # Collect sensor data
        try:
            temp = io.temp()
            humid = io.humid()
            pressure = io.pressure()
            vpd = io.vpd()
            print("[OK]: Getting data from sensor BME280")
        except:
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
        except:
            voltage = 120
            current_val = 2
            active_power = 1
            active_energy = 1
            frequency = 60
            power_factor = 1
            print("[ERROR]: Getting data from module PZEM")

        # Publish data
        client.publish('plant_phase', str(plant_global_phase), retain=True, qos=1)
        client.publish('worg/weather/temp', f'{{"temperature": {temp}}}', retain=True, qos=1)
        client.publish('worg/weather/humid', f'{{"humidity": {humid}}}', retain=True, qos=1)
        client.publish('worg/weather/pressure', f'{{"pressure": {pressure}}}', retain=True, qos=1)
        client.publish('worg/weather/vpd', f'{{"Vapour-pressure deficit": {vpd}}}', retain=True, qos=1)
        print("[OK]: MQTT weather published")

        client.publish('worg/electrical/voltage', f'{{"voltage": {voltage}}}', retain=True, qos=1)
        client.publish('worg/electrical/current', f'{{"current": {current_val}}}', retain=True, qos=1)
        client.publish('worg/electrical/active_power', f'{{"active power": {active_power}}}', retain=True, qos=1)
        client.publish('worg/electrical/active_energy', f'{{"active energy": {active_energy}}}', retain=True, qos=1)
        client.publish('worg/electrical/frequency', f'{{"frequency": {frequency}}}', retain=True, qos=1)
        client.publish('worg/electrical/power_factor', f'{{"power factor": {power_factor}}}', retain=True, qos=1)
        print("[OK]: MQTT electrical published")

        # Publish component status
        client.publish('worg/status/water_pump1', "1" if mcp.pin(3) else "0", retain=True, qos=1)
        client.publish('worg/status/water_pump2', "1" if mcp.pin(2) else "0", retain=True, qos=1)
        client.publish('worg/status/water_pump3', "1" if mcp.pin(1) else "0", retain=True, qos=1)
        client.publish('worg/status/water_pump4', "1" if mcp.pin(0) else "0", retain=True, qos=1)
        client.publish('worg/status/lighting', "1" if mcp.pin(13) else "0", retain=True, qos=1)
        client.publish('worg/status/fan_1', "1" if mcp.pin(15) else "0", retain=True, qos=1)
        client.publish('worg/status/fan_2', "1" if mcp.pin(14) else "0", retain=True, qos=1)
        client.publish('worg/status/humidifier', "1" if mcp.pin(12) else "0", retain=True, qos=1)
        client.publish('worg/status/deshumidifier', "1" if mcp.pin(11) else "0", retain=True, qos=1)
        print("[OK]: MQTT control status published")

        # Plant status
        for plant_id in range(1, 5):
            client.publish(f'worg/plant_status/{plant_id}',
                           f'{{"phase": {plants_watering[plant_id]["phase"]}}}',
                           qos=1)

    except Exception as e:
        print(f"[ERROR]: MQTT cycle failed: {e}")

    finally:
        if client:
            try:
                client.disconnect()
                print("[OK]: MQTT disconnected")
            except:
                pass


# -----------INITIALIZATION-----------#
# Protecao contra reboot no meio da rega
reset_all_pumps()

# Load saved data
load_global_phase()
load_watering_data()
update_global_parameters()

# Connect WiFi
wlan = setup_wifi()

print("[STATUS]: System started")
sleep(10)

# -----------MAIN LOOP-----------#
while True:
    if not wlan.isconnected():
        print("[ERROR]: WiFi disconnected, reconnecting...")
        wlan = setup_wifi()
        if not wlan.isconnected():
            sleep(30)
        else:
            pass

    mqtt_cycle()

    try:
        # TEMPERATURE CONTROL
        temperature = io.temp()

        if temperature < 18:
            io.fan_1(0)
            io.fan_2(0)
            print("[CONTROL]: FAN 1:OFF, FAN 2:OFF")
        elif 18 <= temperature < 22:
            io.fan_1(1)
            io.fan_2(0)
            print("[CONTROL]: FAN 1:ON, FAN 2:OFF")
        else:
            io.fan_1(1)
            io.fan_2(1)
            print("[CONTROL]: FAN 1:ON, FAN 2:ON")

        # VPD CONTROL
        vpd_actual = io.vpd()

        if vpd_actual < vpd_min:
            io.deshumidifier(1)
            io.humidifier(0)
            print("[CONTROL]: HUM:OFF, DESHUM:ON")
        elif vpd_min <= vpd_actual < vpd_max:
            io.deshumidifier(0)
            io.humidifier(0)
            print("[CONTROL]: HUM:OFF, DESHUM:OFF")
        else:
            io.deshumidifier(0)
            io.humidifier(1)
            print("[CONTROL]: HUM:ON, DESHUM:OFF")

        # LIGHTING CONTROL
        HOUR = ds.hour()
        print(f"[STATUS]: Hour: {HOUR}")

        if hour_min <= HOUR < hour_max:
            io.lighting(0)
            print("[CONTROL]: Lightning: OFF")
        else:
            io.lighting(1)
            print("[CONTROL]: Lightning: ON")

        # WATERING CONTROL (check pending commands)
        check_pending_watering()

    except Exception as e:
        print(f"[ERROR]: Control loop: {e}")

    print(f"[STATUS]: Waiting {circle} seconds")
    sleep(circle)