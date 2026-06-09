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
v1.02
"""

# ┌─────────────────────────────────────────────────────────────┐
# │                    MQTT COMMANDS                            │
# ├─────────────────────────────────────────────────────────────┤
# │  GLOBAL (Lighting + VPD)                                    │
# │  └── plant_phase = 0,1,2,3                                  │
# │  WATERING AMOUNT (quantity of water)                        │
# │  ├── worg/watering/plant1 = 0,1,2,3                         │
# │  ├── worg/watering/plant2 = 0,1,2,3                         │
# │  ├── worg/watering/plant3 = 0,1,2,3                         │
# │  └── worg/watering/plant4 = 0,1,2,3                         │
# │  WATERING TRIGGER (user sends 1, system resets to 0)        │
# │  ├── worg/watering/trigger/plant1 = 1 (start) / 0 (done)    │
# │  ├── worg/watering/trigger/plant2 = 1 (start) / 0 (done)    │
# │  ├── worg/watering/trigger/plant3 = 1 (start) / 0 (done)    │
# │  └── worg/watering/trigger/plant4 = 1 (start) / 0 (done)    │
# │  WATERING ERROR (published by system)                       │
# │  ├── worg/watering/error/plant1 = {"error": 1}              │
# │  ├── worg/watering/error/plant2 = {"error": 1}              │
# │  ├── worg/watering/error/plant3 = {"error": 1}              │
# │  └── worg/watering/error/plant4 = {"error": 1}              │
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
circle = 5 * 60

# -----------GLOBAL VARIABLES (Lighting and VPD)-----------#
plant_global_phase = 0
vpd_min = 0.8
vpd_max = 1.2
hour_min = 10
hour_max = 16

# -----------INDIVIDUAL VARIABLES (Watering per plant)-----------#
plants_watering = {
    1: {"phase": 0, "command": 0, "executed": 0},
    2: {"phase": 0, "command": 0, "executed": 0},
    3: {"phase": 0, "command": 0, "executed": 0},
    4: {"phase": 0, "command": 0, "executed": 0},
}

is_watering = False


# -----------FUNCTIONS TO UPDATE GLOBAL PARAMETERS-----------#
def update_global_parameters():
    global vpd_min, vpd_max, hour_min, hour_max
    if plant_global_phase == 1:
        vpd_min, vpd_max, hour_min, hour_max = 0.5, 0.8, 10, 16
    elif plant_global_phase == 2:
        vpd_min, vpd_max, hour_min, hour_max = 0.8, 1.1, 10, 16
    elif plant_global_phase == 3:
        vpd_min, vpd_max, hour_min, hour_max = 1.1, 1.4, 7, 19
    else:
        vpd_min, vpd_max, hour_min, hour_max = 0.8, 1.4, 10, 16
    print(f"[STATUS]: Parameters updated - Phase: {plant_global_phase}")
    print(f"[STATUS]: Lighting: {hour_min}h to {hour_max}h")
    print(f"[STATUS]: VPD: {vpd_min} to {vpd_max}")


# -----------DATA PERSISTENCE-----------#
def save_watering_data():
    try:
        with open('plants_watering.csv', 'w') as f:
            for pid in range(1,5):
                p = plants_watering[pid]
                f.write(f"{pid},{p['phase']},{p['command']},{p['executed']}\n")
        print("[OK]: Watering data saved")
    except Exception as e:
        print(f"[ERROR]: Failed to save watering data: {e}")

def load_watering_data():
    global plants_watering
    try:
        with open('plants_watering.csv', 'r') as f:
            for line in f:
                line = line.strip()
                if line:
                    pid, ph, cmd, exe = map(int, line.split(','))
                    if pid in plants_watering:
                        plants_watering[pid]["phase"] = ph
                        plants_watering[pid]["command"] = cmd
                        plants_watering[pid]["executed"] = exe
        print("[OK]: Watering data loaded")
        print(f"[DEBUG]: plants_watering loaded = {plants_watering}")
    except Exception:
        print("[STATUS]: No watering data previously saved, using default values")

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
            if plant_global_phase not in (0,1,2,3):
                plant_global_phase = 0
        print(f"[OK]: Global phase loaded: {plant_global_phase}")
        update_global_parameters()
    except Exception:
        print("[STATUS]: No global phase saved, using default (0)")


# -----------WATERING EXECUTION (lógica do v0.4)-----------#
def reset_all_pumps():
    for pid in range(1,5):
        getattr(io, f'water_pump_{pid}')(0)
    print("[PROTECTION]: All pumps turned off")

def execute_watering_cycle(plant_id, cycles, water_pump):
    global is_watering
    is_watering = True
    success = False
    try:
        total_cycles = cycles
        while cycles > 0:
            print(f"[CONTROL]: Plant {plant_id} - Cycle {cycles} of {total_cycles}")
            water_pump(1)
            sleep(10)
            water_pump(0)
            if cycles > 1:
                sleep(10)
            cycles -= 1
        print(f"[CONTROL]: Plant {plant_id} - Watering completed")
        success = True
    except Exception as e:
        print(f"[ERROR]: Plant {plant_id} - Watering interrupted: {e}")
        water_pump(0)
        # publicar erro (tenta, se WiFi disponível)
        if wlan.isconnected():
            try:
                mqtt_publish_error(plant_id)
            except:
                pass
    finally:
        is_watering = False
        return success

def water_plant(plant_id):
    state = plants_watering[plant_id]["phase"]
    print(f"[CONTROL]: Watering plant {plant_id} - Amount: {state}")
    cycles = {0:0, 1:4, 2:8, 3:22}.get(state, 0)

    if cycles > 0:
        pump = getattr(io, f'water_pump_{plant_id}')
        success = execute_watering_cycle(plant_id, cycles, pump)
        if success:
            plants_watering[plant_id]["command"] = 0
            plants_watering[plant_id]["executed"] = 0
            save_watering_data()
            if wlan.isconnected():
                try:
                    mqtt_publish_trigger(plant_id, 0)
                except:
                    pass
            print(f"[CONTROL]: Plant {plant_id} - Watering successful")
        else:
            plants_watering[plant_id]["command"] = 0
            plants_watering[plant_id]["executed"] = 1
            save_watering_data()
            print(f"[CONTROL]: Plant {plant_id} - Watering failed, blocked")
    else:
        print(f"[CONTROL]: Plant {plant_id} - Phase 0, nothing to do")
        plants_watering[plant_id]["command"] = 0
        plants_watering[plant_id]["executed"] = 0
        save_watering_data()
        if wlan.isconnected():
            try:
                mqtt_publish_trigger(plant_id, 0)
            except:
                pass

def check_pending_watering():
    global is_watering
    if is_watering:
        return
    for pid in range(1,5):
        if plants_watering[pid]["command"] == 1 and plants_watering[pid]["executed"] == 0:
            print(f"[CONTROL]: Executing pending watering for plant {pid}")
            if wlan.isconnected():
                try:
                    mqtt_publish_trigger(pid, 1)
                except:
                    pass
            water_plant(pid)
            sleep(30)
            break


# -----------MQTT AUXILIARY (conecta, publica, desconecta)-----------#
def mqtt_publish_trigger(plant_id, status):
    client = None
    try:
        client = MQTTClient(MQTT_ID, server=MQTT_SERVER, port=MQTT_PORT,
                           user=MQTT_USER, password=MQTT_PASSWORD, keepalive=60)
        client.connect()
        client.publish(f'worg/watering/trigger/plant{plant_id}', str(status), retain=True, qos=1)
        client.disconnect()
        print(f"[MQTT]: Published trigger plant {plant_id} = {status}")
    except Exception as e:
        print(f"[ERROR]: Failed to publish trigger for plant {plant_id}: {e}")
    finally:
        if client:
            try:
                client.disconnect()
            except:
                pass

def mqtt_publish_error(plant_id):
    client = None
    try:
        client = MQTTClient(MQTT_ID, server=MQTT_SERVER, port=MQTT_PORT,
                           user=MQTT_USER, password=MQTT_PASSWORD, keepalive=60)
        client.connect()
        client.publish(f'worg/watering/error/plant{plant_id}', '{"error": 1}', retain=True, qos=1)
        client.disconnect()
        print(f"[MQTT]: Published error plant {plant_id}")
    except Exception as e:
        print(f"[ERROR]: Failed to publish error for plant {plant_id}: {e}")
    finally:
        if client:
            try:
                client.disconnect()
            except:
                pass

def mqtt_publish_sensors():
    """Conecta, publica dados de sensores e status, desconecta."""
    client = None
    try:
        client = MQTTClient(MQTT_ID, server=MQTT_SERVER, port=MQTT_PORT,
                           user=MQTT_USER, password=MQTT_PASSWORD, keepalive=60)
        client.connect()
        print("[OK]: MQTT connected for sensor publishing")

        # Leitura dos sensores
        try:
            temp = io.temp()
            humid = io.humid()
            pressure = io.pressure()
            vpd = io.vpd()
            print("[OK]: Getting data from sensor BME280")
        except:
            temp, humid, pressure, vpd = 25, 60, 950, 1
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
            voltage, current_val, active_power, active_energy, frequency, power_factor = 120, 2, 1, 1, 60, 1
            print("[ERROR]: Getting data from module PZEM")

        # Publicações
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

        for pid in range(1,5):
            client.publish(f'worg/plant_status/{pid}', f'{{"phase": {plants_watering[pid]["phase"]}}}', qos=1)
        print("[OK]: MQTT plant status published")

    except Exception as e:
        print(f"[ERROR]: MQTT publish cycle failed: {e}")

    finally:
        if client:
            try:
                client.disconnect()
                print("[OK]: MQTT disconnected after publish")
            except:
                pass


def mqtt_receive_commands():
    """Conecta, escuta comandos por 2 segundos, desconecta."""
    client = None
    commands = []
    try:
        client = MQTTClient(MQTT_ID, server=MQTT_SERVER, port=MQTT_PORT,
                           user=MQTT_USER, password=MQTT_PASSWORD, keepalive=60)
        client.set_callback(lambda t, m: commands.append((t.decode('utf-8'), m.decode('utf-8'))))
        client.connect()
        print("[OK]: MQTT connected for commands")

        # Subscrições
        client.subscribe('plant_phase', qos=1)
        for pid in range(1,5):
            client.subscribe(f'worg/watering/plant{pid}', qos=1)
            client.subscribe(f'worg/watering/trigger/plant{pid}', qos=1)

        print("[MQTT]: Waiting for commands...")
        start = time.time()
        while time.time() - start < 2:
            client.check_msg()
            sleep(0.1)

    except Exception as e:
        print(f"[ERROR]: MQTT receive cycle failed: {e}")

    finally:
        if client:
            try:
                client.disconnect()
                print("[OK]: MQTT disconnected after commands")
            except:
                pass

    return commands


# -----------PROCESS RECEIVED COMMANDS-----------#
def process_mqtt_commands(commands):
    global plant_global_phase
    for topic, value in commands:
        if topic == 'plant_phase':
            try:
                new = int(value)
                if 0 <= new <= 3:
                    plant_global_phase = new
                    update_global_parameters()
                    save_global_phase()
                    print(f"[MQTT]: Global phase changed to {new}")
            except:
                pass
        elif topic.startswith('worg/watering/') and not any(topic.startswith(p) for p in ('worg/watering/trigger/','worg/watering/error/')):
            try:
                pid = int(topic.split('/')[-1].replace('plant',''))
                new_phase = int(value)
                if 0 <= new_phase <= 3 and pid in plants_watering:
                    plants_watering[pid]["phase"] = new_phase
                    save_watering_data()
                    print(f"[MQTT]: Plant {pid} - Watering amount changed to {new_phase}")
            except:
                pass
        elif topic.startswith('worg/watering/trigger/'):
            try:
                pid = int(topic.split('/')[-1].replace('plant',''))
                trig = int(value)
                if trig == 1:
                    if is_watering:
                        print(f"[MQTT]: Plant {pid} - System busy, command ignored")
                    elif plants_watering[pid]["command"] == 1:
                        print(f"[MQTT]: Plant {pid} - Already pending")
                    elif plants_watering[pid]["executed"] == 1:
                        print(f"[MQTT]: Plant {pid} - Blocked (error), send 0 to reset")
                    else:
                        plants_watering[pid]["command"] = 1
                        save_watering_data()
                        print(f"[MQTT]: Plant {pid} - Watering command saved")
                elif trig == 0:
                    plants_watering[pid]["command"] = 0
                    plants_watering[pid]["executed"] = 0
                    save_watering_data()
                    if wlan.isconnected():
                        try:
                            mqtt_publish_trigger(pid, 0)
                        except:
                            pass
                    print(f"[MQTT]: Plant {pid} - Manual reset")
                else:
                    print(f"[MQTT]: Plant {pid} - Invalid trigger {trig}")
            except:
                pass


# -----------INTERNET CONNECTION (não bloqueante)-----------#
def setup_wifi():
    global wlan
    try:
        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)
        print("[STATUS]: Connecting to WiFi...")
        if not wlan.isconnected():
            wlan.connect(SSID, PASSWORD)
            timeout = 15
            start = time.time()
            while not wlan.isconnected() and (time.time() - start) < timeout:
                print(".", end="")
                sleep(1)
            print()
            if wlan.isconnected():
                print(f"[OK]: WiFi connected! IP: {wlan.ifconfig()[0]}")
                print(f"[OK]: Signal: {wlan.status('rssi')} dBm")
            else:
                print("[ERROR]: WiFi failed!")
    except Exception as e:
        print(f"[ERROR]: WiFi setup error: {e}")
        wlan = None
    return wlan


# -----------INITIALIZATION-----------#
reset_all_pumps()
load_global_phase()
load_watering_data()
update_global_parameters()

# Tenta conectar WiFi (se falhar, continua sem)
wlan = setup_wifi()
if wlan is None or not wlan.isconnected():
    print("[WARNING]: No WiFi connection, running in offline mode")

print("[STATUS]: System started")
sleep(10)

# -----------MAIN LOOP-----------#
while True:
    # Verifica WiFi apenas se já estava conectado, sem forçar reconexão pesada
    if wlan is not None:
        if not wlan.isconnected():
            print("[WARNING]: WiFi lost, trying to reconnect...")
            try:
                wlan.disconnect()
                wlan.connect(SSID, PASSWORD)
                timeout = 10
                start = time.time()
                while not wlan.isconnected() and (time.time() - start) < timeout:
                    sleep(0.5)
                if wlan.isconnected():
                    print(f"[OK]: WiFi reconnected! IP: {wlan.ifconfig()[0]}")
                else:
                    print("[WARNING]: WiFi still disconnected, continuing offline")
            except Exception as e:
                print(f"[WARNING]: WiFi reconnect error: {e}")

    # ===== MQTT (apenas se WiFi estiver conectado) =====
    if wlan is not None and wlan.isconnected():
        try:
            # 1. Receber comandos MQTT
            cmds = mqtt_receive_commands()
            if cmds:
                process_mqtt_commands(cmds)
        except Exception as e:
            print(f"[WARNING]: MQTT receive failed: {e}")

        try:
            # 2. Publicar dados de sensores e status
            mqtt_publish_sensors()
        except Exception as e:
            print(f"[WARNING]: MQTT publish failed: {e}")
    else:
        print("[INFO]: Offline mode - MQTT skipped")

    # ===== CONTROLES LOCAIS (sempre executam, independente de WiFi) =====
    try:
        temp = io.temp()
        if temp < 18:
            io.fan_1(0)
            io.fan_2(0)
        elif 18 <= temp < 22:
            io.fan_1(1)
            io.fan_2(0)
        else:
            io.fan_1(1)
            io.fan_2(1)

        vpd_actual = io.vpd()
        if vpd_actual < vpd_min:
            io.deshumidifier(1)
            io.humidifier(0)
        elif vpd_min <= vpd_actual < vpd_max:
            io.deshumidifier(0)
            io.humidifier(0)
        else:
            io.deshumidifier(0)
            io.humidifier(1)

        hour = ds.hour()
        if hour_min <= hour < hour_max:
            io.lighting(0)
        else:
            io.lighting(1)

        # Verificar regas pendentes
        check_pending_watering()

    except Exception as e:
        print(f"[ERROR]: Control loop: {e}")

    print(f"[STATUS]: Waiting {circle} seconds")
    sleep(circle)