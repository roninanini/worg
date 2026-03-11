The Worg project is an embedded system for environmental monitoring of a greenhouse with 4 plants. By reading soil moisture and environmental conditions, the system controls humidity levels, temperature, VPD (Vapour-pressure Deficit), and the automatic watering of the plants. 
The architecture is based on an ESP32 programmed in MicroPython, communication via MQTT protocol with Mosquitto Broker, data persistence in InfluxDB, and custom visualization in Grafana, all integrated in this WordPress site for project presentation.

All data below is updated in real time every 10 minutes: https://roni.engineer/

