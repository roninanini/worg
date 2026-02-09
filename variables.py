from machine import I2C, Pin, UART
from time import sleep
import Libs.mcp23017
import Libs.bme280
from Libs.soil import sensor_soil
from Libs.pzem import PZEM
import math
from Libs.ds3231 import DS3231

i2c = I2C(0, scl=Pin(22), sda=Pin(21), freq=400000)
mcp = Libs.mcp23017.MCP23017(i2c, 0x27)
uart = UART(2, baudrate=9600,timeout=500)
dev = PZEM(uart=uart,addr=0x01)
bme = Libs.bme280.BME280(i2c=i2c)
ds = DS3231(i2c)

#Address of mcp: 39 (dec) = 27 (hex)
#Address of bme: 118 (dec) = 76 (hex)
#Address of ds: 104 (dec) = 68 (hex)

class IO:
    def __init__(self):
        self.led = Pin(2, Pin.OUT)
        self.VPD = 0
        self.VP = 0
        self.VPL = 0
        # Adicione estas variáveis para armazenar estados
        self.water_pump_1_state = 0
        self.water_pump_2_state = 0
        self.water_pump_3_state = 0
        self.water_pump_4_state = 0
        self.lighting_state = 0
        self.fan_1_state = 0
        self.fan_2_state = 0
        self.humidifier_state = 0
        self.deshumidifier_state = 0

    # --------------- OUTPUTS ---------------#
    def water_pump_1(self, state):
        mcp.pin(3, mode=0, value=state)
        self.water_pump_1_state = state  # Armazena o estado

    def water_pump_2(self, state):
        mcp.pin(2, mode=0, value=state)
        self.water_pump_2_state = state

    def water_pump_3(self, state):
        mcp.pin(1, mode=0, value=state)
        self.water_pump_3_state = state

    def water_pump_4(self, state):
        mcp.pin(0, mode=0, value=state)
        self.water_pump_4_state = state

    def lighting(self, state):
        mcp.pin(13, mode=0, value=state)
        self.lighting_state = state

    def fan_1(self, state):
        mcp.pin(15, mode=0, value=state)
        self.fan_1_state = state

    def fan_2(self, state):
        mcp.pin(14, mode=0, value=state)
        self.fan_2_state = state

    def humidifier(self, state):
        mcp.pin(12, mode=0, value=state)
        self.humidifier_state = state

    def deshumidifier(self, state):
        mcp.pin(11, mode=0, value=state)
        self.deshumidifier_state = state

    # --------------- GETTERS PARA STATUS ---------------#
    def get_water_pump_1_status(self):
        return self.water_pump_1_state

    def get_water_pump_2_status(self):
        return self.water_pump_2_state

    def get_water_pump_3_status(self):
        return self.water_pump_3_state

    def get_water_pump_4_status(self):
        return self.water_pump_4_state

    def get_lighting_status(self):
        return self.lighting_state

    def get_fan_1_status(self):
        return self.fan_1_state

    def get_fan_2_status(self):
        return self.fan_2_state

    def get_humidifier_status(self):
        return self.humidifier_state

    def get_deshumidifier_status(self):
        return self.deshumidifier_state

#--------------- INPUTS ---------------#
    def soil_1(self):
        return sensor_soil.AVERAGE_PLANT1
    def soil_2(self):
        return sensor_soil.AVERAGE_PLANT2
    def soil_3(self):
        return sensor_soil.AVERAGE_PLANT3
    def soil_4(self):
        return sensor_soil.AVERAGE_PLANT4
    def temp(self):
        read_temp, _, _ = bme.read_compensated_data()
        return read_temp
    def pressure(self):
        _, read_pressure, _ = bme.read_compensated_data()
        return read_pressure / 100
    def humid(self):
        _, _, read_humid = bme.read_compensated_data()
        return read_humid
    def vpd(self):
        # vapor pressure of air (VP):
        self.VP = 0.61078 * math.exp(17.27 * self.temp() / (self.temp() + 237.03)) * (self.humid()/100)
        # vapor pressure in the leaf (VPL):
        self.VPL = 0.61078 * math.exp(17.27 * self.temp() / (self.temp() + 237.03))
        # vapor pressure deficit (VPD):
        self.VPD = self.VPL - self.VP
        return self.VPD
    def hour(self, hour=None):
        #(year, month, mday, wday, hour, minute, second, 0)
        return ds.datetime()

#--------------- ETC ---------------#
    def voltage(self):
        dev.read()
        return dev.getVoltage()
    def current(self):
        dev.read()
        return dev.getCurrent()
    def active_power(self):
        dev.read()
        return dev.getActivePower()
    def active_energy(self):
        dev.read()
        return dev.getActiveEnergy()
    def frequency(self):
        dev.read()
        return dev.getFrequency()
    def power_factor(self):
        dev.read()
        return dev.getPowerFactor()





