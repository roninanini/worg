import network
from time import sleep
import time
from variables import IO
from Libs.umqtt_simple import MQTTClient
from Libs.ds3231 import DS3231
from machine import I2C, Pin, ADC
import Libs.mcp23017
from Libs.soil import sensor_soil

# -----------ATRIBUTES-----------#
io = IO()
SSID = 'PODER POPULAR - 2.4G'
PASSWORD = 'morganachico31'
MQTT_ID = 'worg_esp'
MQTT_SERVER = '147.93.12.223'
MQTT_PORT = 1883
MQTT_USER = 'roninanini'
MQTT_PASSWORD = '7$eVY:F5CC>oY6~ l[LG`1z)9*C[c.'
i2c = I2C(0, scl=Pin(22), sda=Pin(21), freq=400000)
mcp = Libs.mcp23017.MCP23017(i2c, 0x27)
ds = DS3231(i2c)
circle = 5*60

# -----------INTERNET CONECTION ----------#
def setup_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    print("Conectando ao WiFi...")
    print(f"SSID: {SSID}")
    if not wlan.isconnected():
        wlan.connect(SSID, PASSWORD)
        print("Tentando conexão...")
    return wlan

def write_data(topic, message):
    topic = topic.decode('utf-8')
    value = message.decode('utf-8')
    plant1, plant2, plant3, plant4 = read_data()
    if topic == 'worg/phase_plant1':
        plant1 = value
    elif topic == 'worg/phase_plant2':
        plant2 = value
    elif topic == 'worg/phase_plant3':
        plant3 = value
    elif topic == 'worg/phase_plant4':
        plant4 = value

    with open('data.csv', 'w') as f:
        f.write(f'{plant1},{plant2},{plant3},{plant4}')

def read_data():
    try:
        with open('data.csv', 'r') as f:
            line = f.read().split(',')
            return line[0], line[1], line[2], line[3]
    except Exception as e:
        return "0", "0", "0", "0"

client_mqtt = MQTTClient(MQTT_ID, server=MQTT_SERVER, port=MQTT_PORT, user=MQTT_USER, password=MQTT_PASSWORD, keepalive=300)
client_mqtt.set_callback(write_data)

def water_plant(soil_moisture, state, water_pump, plant_name=""):
    """Water a plant based on soil moisture and state"""
    if soil_moisture < 10:
        print(f"Watering {plant_name} - State: {state}")
        # Determine watering cycles based on state
        if state == 0:
            cycles = 0
        elif state == 1:
            cycles = 2
        elif state == 2:
            cycles = 4
        elif state == 3:
            cycles = 6
        else:
            cycles = 0

        # Execute watering cycles
        while cycles > 0:
            water_pump(1)  # Turn pump ON
            sleep(10)  # Water for 10 seconds
            water_pump(0)  # Turn pump OFF
            sleep(10)  # Pause for 10 seconds
            cycles -= 1  # Decrement counter

sleep(10)
print("Leitura individual :", sensor_soil.PLANT_1.read(), sensor_soil.PLANT_2.read(), sensor_soil.PLANT_3.read(), sensor_soil.PLANT_4.read())
print("Leitura media: ", sensor_soil.AVERAGE_PLANT1, sensor_soil.AVERAGE_PLANT2, sensor_soil.AVERAGE_PLANT3, sensor_soil.AVERAGE_PLANT4)

while True:
    wlan = setup_wifi()
    timeout = 10
    start_time_wifi = time.time()

    while not wlan.isconnected():
        if time.time() - start_time_wifi > timeout:
            break
        sleep(1)

    if wlan.isconnected():
        try:
            client_mqtt.connect()
            client_mqtt.subscribe('worg/phase_plant1', qos=1)
            client_mqtt.subscribe('worg/phase_plant2', qos=1)
            client_mqtt.subscribe('worg/phase_plant3', qos=1)
            client_mqtt.subscribe('worg/phase_plant4', qos=1)
            client_mqtt.check_msg()

            try:
                temp = io.temp()
                humid = io.humid()
                pressure = io.pressure()
                vpd = io.vpd()
            except Exception as e:
                temp = 25
                humid = 60
                pressure = 950
                vpd = 1
            try:
                voltage = io.voltage()
                current_val = io.current()
                active_power = io.active_power()
                active_energy = io.active_energy()
                frequency = io.frequency()
                power_factor = io.power_factor()
            except Exception as e:
                voltage = 120
                current_val = 2
                active_power = 1
                active_energy = 1
                frequency = 60
                power_factor = 1

            # SENSORES DE SOLO
            try:
                soil_1 = str(io.soil_1())
            except Exception as e:
                soil_1 = '4095'
            try:
                soil_2 = str(io.soil_2())
            except Exception as e:
                soil_2 = '4095'
            try:
                soil_3 = str(io.soil_3())
            except Exception as e:
                soil_3 = '4095'
            try:
                soil_4 = str(io.soil_4())
            except Exception as e:
                soil_4 = '4095'

            # -----------POINTS OF WEATHER TO GRAFANA -----------#
            client_mqtt.publish('worg/weather/temp', f'{{"temperature": {temp}}}', retain=False, qos=1)
            client_mqtt.publish('worg/weather/humid', f'{{"humidity": {humid}}}', retain=False, qos=1)
            client_mqtt.publish('worg/weather/pressure', f'{{"pressure": {pressure}}}', retain=False, qos=1)
            client_mqtt.publish('worg/weather/vpd', f'{{"Vapour-pressure deficit": {vpd}}}', retain=False, qos=1)

            # -----------ELECTRICAL POINTS TO GRAFANA -----------#
            client_mqtt.publish('worg/electrical/voltage', f'{{"voltage": {voltage}}}', retain=False, qos=1)
            client_mqtt.publish('worg/electrical/current', f'{{"current": {current_val}}}', retain=False, qos=1)
            client_mqtt.publish('worg/electrical/active_power', f'{{"active power": {active_power}}}', retain=False, qos=1)
            client_mqtt.publish('worg/electrical/active_energy', f'{{"active energy": {active_energy}}}', retain=False, qos=1)
            client_mqtt.publish('worg/electrical/frequency', f'{{"frequency": {frequency}}}', retain=False, qos=1)
            client_mqtt.publish('worg/electrical/power_factor', f'{{"power factor": {power_factor}}}', retain=False, qos=1)

            # -----------POINTS OF SOIL TO GRAFANA -----------#

            client_mqtt.publish('worg/soil1', f'{{"soil_moisture 1": {soil_1}}}', retain=False, qos=1)
            client_mqtt.publish('worg/soil2', f'{{"soil_moisture 2": {soil_2}}}', retain=False, qos=1)
            client_mqtt.publish('worg/soil3', f'{{"soil_moisture 3": {soil_3}}}', retain=False, qos=1)
            client_mqtt.publish('worg/soil4', f'{{"soil_moisture 4": {soil_4}}}', retain=False, qos=1)

        except Exception as e:
            try:
                client_mqtt.disconnect()
            except:
                pass

    try:
        # CONTROL
        if io.temp() < 18:
            # Too cold
            io.fan_1(0)
            io.fan_2(0)
            try:
                client_mqtt.publish('worg/status/fan_1', f'{{"Fan 01": 0}}', retain=True,qos=1)
                client_mqtt.publish('worg/status/fan_2', f'{{"Fan 02": 0}}', retain=True,qos=1)
            except Exception as e:
                pass
        elif 18 <= io.temp() < 22:
            # Slightly warm - minimal cooling
            io.fan_1(1)
            io.fan_2(0)
            try:
                client_mqtt.publish('worg/status/fan_1', f'{{"Fan 01": 1}}', retain=True,qos=1)
                client_mqtt.publish('worg/status/fan_2', f'{{"Fan 02": 0}}', retain=True,qos=1)
            except Exception as e:
                pass
        elif 22 <= io.temp() < 25:
            # Moderately warm - more cooling
            io.fan_1(1)
            io.fan_2(1)
            try:
                client_mqtt.publish('worg/status/fan_1', f'{{"Fan 01": 1}}', retain=True,qos=1)
                client_mqtt.publish('worg/status/fan_2', f'{{"Fan 02": 1}}', retain=True,qos=1)
            except Exception as e:
                pass
        else:
            # Too hot - maximum cooling
            io.fan_1(1)
            io.fan_2(1)
            try:
                client_mqtt.publish('worg/status/fan_1', f'{{"Fan 01": 1}}', retain=True, qos=1)
                client_mqtt.publish('worg/status/fan_2', f'{{"Fan 02": 1}}', retain=True, qos=1)
            except Exception as e:
                pass

        if io.vpd() < 0.8:
            io.deshumidifier(1)
            io.humidifier(0)
            try:
                client_mqtt.publish('worg/status/deshumidifier', f'{{"Deshumidifier": 1}}', retain=True, qos=1)
                client_mqtt.publish('worg/status/humidifier', f'{{"Humidifier": 0}}',retain=True, qos=1)
            except Exception as e:
                pass
        elif 0.8 <= io.vpd() < 1.2:
            io.deshumidifier(0)
            io.humidifier(0)
            try:
                client_mqtt.publish('worg/status/deshumidifier', f'{{"Deshumidifier": 0}}', retain=True, qos=1)
                client_mqtt.publish('worg/status/humidifier', f'{{"Humidifier": 0}}', retain=True, qos=1)
            except Exception as e:
                pass
        else:
            io.deshumidifier(0)
            io.humidifier(1)
            try:
                client_mqtt.publish('worg/status/deshumidifier', f'{{"Deshumidifier": 0}}', retain=True, qos=1)
                client_mqtt.publish('worg/status/humidifier', f'{{"Humidifier": 1}}', retain=True, qos=1)
            except Exception as e:
                pass

        # Light control
        HOUR = ds.hour()
        if 10 <= HOUR < 16:
            io.lighting(0)
            try:
                client_mqtt.publish('worg/status/lighting', f'{{"Lighting": 0}}',retain=True, qos=1)
            except Exception as e:
                pass
        else:
            io.lighting(1)
            try:
                client_mqtt.publish('worg/status/lighting', f'{{"Lighting": 1}}',retain=True, qos=1)
            except Exception as e:
                pass

        #Usage for all 4 plants
        states = read_data()
        water_plant(io.soil_1(), int(states[0]), io.water_pump_1, "Plant 1")
        try:
            client_mqtt.publish('worg/status/water_pump1', f'{{"Water Pump 01": {"1" if mcp.pin(3) else "0"}}}',retain=True, qos=1)
        except Exception as e:
            pass
        water_plant(io.soil_2(), int(states[1]), io.water_pump_2, "Plant 2")
        try:
            client_mqtt.publish('worg/status/water_pump2', f'{{"Water Pump 02": {"1" if mcp.pin(2) else "0"}}}',retain=True, qos=1)
        except Exception as e:
            pass
        water_plant(io.soil_3(), int(states[2]), io.water_pump_3, "Plant 3")
        try:
            client_mqtt.publish('worg/status/water_pump3', f'{{"Water Pump 03": {"1" if mcp.pin(1) else "0"}}}',retain=True, qos=1)
        except Exception as e:
            pass
        water_plant(io.soil_4(), int(states[3]), io.water_pump_4, "Plant 4")
        try:
            client_mqtt.publish('worg/status/water_pump4', f'{{"Water Pump 04": {"1" if mcp.pin(0) else "0"}}}',retain=True, qos=1)
        except Exception as e:
            pass
        print("Leitura media: ", sensor_soil.AVERAGE_PLANT1, sensor_soil.AVERAGE_PLANT2, sensor_soil.AVERAGE_PLANT3, sensor_soil.AVERAGE_PLANT4)


    except Exception as e:
        pass

    sleep(circle)