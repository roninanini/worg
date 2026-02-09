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

You can access the source code on site: $$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$
"""

from machine import Pin, ADC
from time import sleep
import time
import _thread
import gc

class Soil:
    def __init__(self):
        # ATRIBUTES
        self.PLANT_1 = ADC(Pin(34))
        self.PLANT_2 = ADC(Pin(35))
        self.PLANT_3 = ADC(Pin(32))
        self.PLANT_4 = ADC(Pin(33))
        self.pack_time = 5*60 #seconds
        self.read_by_pack = 10 #seconds

        # configure ADC ports to 0-3.3V (ESP32)
        self.PLANT_1.atten(ADC.ATTN_11DB)
        self.PLANT_2.atten(ADC.ATTN_11DB)
        self.PLANT_3.atten(ADC.ATTN_11DB)
        self.PLANT_4.atten(ADC.ATTN_11DB)

        # creating lists to store values
        self.LIST_PLANT1 = []
        self.LIST_PLANT2 = []
        self.LIST_PLANT3 = []
        self.LIST_PLANT4 = []

        # making value 0 to average value
        self.AVERAGE_PLANT1 = 4095
        self.AVERAGE_PLANT2 = 4095
        self.AVERAGE_PLANT3 = 4095
        self.AVERAGE_PLANT4 = 4095

        # defining the initial time
        self.thread_started = False
        self.start_time = time.time()

    def soil_loop(self):
        self.thread_started = True
        while True:
            gc.collect()
            # reading the value of sensors
            value_PLANT1 = self.PLANT_1.read()
            value_PLANT2 = self.PLANT_2.read()
            value_PLANT3 = self.PLANT_3.read()
            value_PLANT4 = self.PLANT_4.read()

            # storing the values in the list
            self.LIST_PLANT1.append(value_PLANT1)
            self.LIST_PLANT2.append(value_PLANT2)
            self.LIST_PLANT3.append(value_PLANT3)
            self.LIST_PLANT4.append(value_PLANT4)

            # verifing the time
            if time.time() - self.start_time >= (self.pack_time):
                # calculating the average of the reads
                self.AVERAGE_PLANT1 = sum(self.LIST_PLANT1) / len(self.LIST_PLANT1)
                self.AVERAGE_PLANT2 = sum(self.LIST_PLANT2) / len(self.LIST_PLANT2)
                self.AVERAGE_PLANT3 = sum(self.LIST_PLANT3) / len(self.LIST_PLANT3)
                self.AVERAGE_PLANT4 = sum(self.LIST_PLANT4) / len(self.LIST_PLANT4)

                # reboot lists and time
                self.LIST_PLANT1 = []
                self.LIST_PLANT2 = []
                self.LIST_PLANT3 = []
                self.LIST_PLANT4 = []
                self.start_time = time.time()

            # waiting 1 sec to next read
            sleep(self.read_by_pack)

    def get_soil(self):
        return self.AVERAGE_PLANT1, self.AVERAGE_PLANT2, self.AVERAGE_PLANT3, self.AVERAGE_PLANT4

sensor_soil = Soil()
_thread.start_new_thread(sensor_soil.soil_loop, ())



