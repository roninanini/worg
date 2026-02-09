# test_adc.py
from machine import ADC, Pin
from time import sleep

PLANT_1 = ADC(Pin(25))
PLANT_2 = ADC(Pin(26))
PLANT_3 = ADC(Pin(27))
PLANT_4 = ADC(Pin(14))

PLANT_1.atten(ADC.ATTN_11DB)
PLANT_2.atten(ADC.ATTN_11DB)
PLANT_3.atten(ADC.ATTN_11DB)
PLANT_4.atten(ADC.ATTN_11DB)

while True:
    print(PLANT_1.read(), PLANT_2.read(), PLANT_3.read(), PLANT_4.read())
    sleep(1)