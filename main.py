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

# ┌─────────────────────────────────────────────────────────────┐
# │                    COMANDOS MQTT                            │
# ├─────────────────────────────────────────────────────────────┤
# │                                                             │
# │  GLOBAL (Iluminação + VPD)                                  │
# │  └── plant_phase = 0,1,2,3                                  │
# │                                                             │
# │  REGA (quantidade de água)                                  │
# │  ├── worg/watering/plant1 = 0,1,2,3                         │
# │  ├── worg/watering/plant2 = 0,1,2,3                         │
# │  ├── worg/watering/plant3 = 0,1,2,3                         │
# │  └── worg/watering/plant4 = 0,1,2,3                         │
# │                                                             │
# │  OVERRIDE (forçar dias acumulados)                          │
# │  ├── worg/days/plant1 = 0,1,2,3                             │
# │  ├── worg/days/plant2 = 0,1,2,3                             │
# │  ├── worg/days/plant3 = 0,1,2,3                             │
# │  └── worg/days/plant4 = 0,1,2,3                             │
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
import webrepl

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

# -----------VARIAVEIS GLOBAIS (Iluminacao e VPD)-----------#
# Controlado pelo topico MQTT 'plant_phase' (valor unico)
plant_global_phase = 0

# Variaveis que serao atualizadas conforme a fase global
vpd_min = 0.8
vpd_max = 1.2
hour_min = 10
hour_max = 16

# -----------VARIAVEIS INDIVIDUAIS (Rega de cada planta)-----------#
# Cada planta tem:
#   phase: quantidade de agua (0,1,2,3) - controlado por MQTT individual (worg/watering/plantX)
#   dias: dias acumulados (0,1,2,3) - automatico ou override manual (worg/days/plantX)
plantas_rega = {
    1: {"phase": 0, "dias": 0},
    2: {"phase": 0, "dias": 0},
    3: {"phase": 0, "dias": 0},
    4: {"phase": 0, "dias": 0},
}

# Controle para nao regar multiplas vezes no mesmo dia
rega_executada_hoje = False
ultimo_dia = None  # Armazena o ultimo dia registrado (1-31)

# Variavel para armazenar comandos recebidos durante o ciclo MQTT
comandos_recebidos = []


# -----------FUNCOES PARA ATUALIZAR PARAMETROS GLOBAIS-----------#
def atualizar_parametros_globais():
    """Atualiza VPD e horarios baseado na fase global"""
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
    else:  # phase 0
        vpd_min = 0.8
        vpd_max = 1.2
        hour_min = 10
        hour_max = 16

    print(f"[STATUS]: Parametros atualizados - Phase: {plant_global_phase}")
    print(f"[STATUS]: Iluminacao: {hour_min}h as {hour_max}h")
    print(f"[STATUS]: VPD: {vpd_min} a {vpd_max}")


# -----------FUNCOES PARA SALVAR E LER DADOS DAS PLANTAS (REGA)-----------#
def salvar_dados_rega():
    """Salva os dados de phase e dias de cada planta, alem do ultimo_dia e rega_executada_hoje"""
    try:
        with open('plantas_rega.csv', 'w') as f:
            # Salva dados das plantas
            for planta_id in range(1, 5):
                phase = plantas_rega[planta_id]["phase"]
                dias = plantas_rega[planta_id]["dias"]
                f.write(f"{planta_id},{phase},{dias}\n")
            # Salva informacoes de controle na ultima linha
            f.write(f"CONTROL,{ultimo_dia if ultimo_dia is not None else 0},{1 if rega_executada_hoje else 0}\n")
        print("[OK]: Dados de rega e controle salvos")
    except Exception as e:
        print(f"[ERROR]: Falha ao salvar dados de rega: {e}")

def carregar_dados_rega():
    """Carrega os dados de phase e dias de cada planta, alem do ultimo_dia e rega_executada_hoje"""
    global plantas_rega, ultimo_dia, rega_executada_hoje
    try:
        with open('plantas_rega.csv', 'r') as f:
            linhas = f.readlines()
            for linha in linhas:
                linha = linha.strip()
                if linha:
                    partes = linha.split(',')
                    if len(partes) == 3:
                        if partes[0] == "CONTROL":
                            # Linha de controle
                            ultimo_dia_valor = int(partes[1])
                            rega_executada_valor = int(partes[2])
                            if ultimo_dia_valor != 0:
                                ultimo_dia = ultimo_dia_valor
                            rega_executada_hoje = (rega_executada_valor == 1)
                        else:
                            # Dados das plantas
                            planta_id = int(partes[0])
                            phase = int(partes[1])
                            dias = int(partes[2])
                            if planta_id in plantas_rega:
                                plantas_rega[planta_id]["phase"] = phase
                                plantas_rega[planta_id]["dias"] = dias
        print("[OK]: Dados de rega e controle carregados")
        if ultimo_dia is not None:
            print(f"[STATUS]: ultimo_dia recuperado: {ultimo_dia}")
        print(f"[STATUS]: rega_executada_hoje recuperado: {rega_executada_hoje}")
    except Exception as e:
        print(f"[STATUS]: Nenhum dado de rega salvo anteriormente, usando valores padrao")

def salvar_fase_global():
    """Salva a fase global no arquivo"""
    try:
        with open('fase_global.csv', 'w') as f:
            f.write(str(plant_global_phase))
        print("[OK]: Fase global salva")
    except Exception as e:
        print(f"[ERROR]: Falha ao salvar fase global: {e}")

def carregar_fase_global():
    """Carrega a fase global do arquivo"""
    global plant_global_phase
    try:
        with open('fase_global.csv', 'r') as f:
            plant_global_phase = int(f.read().strip())
            if plant_global_phase < 0 or plant_global_phase > 3:
                plant_global_phase = 0
        print(f"[OK]: Fase global carregada: {plant_global_phase}")
        atualizar_parametros_globais()
    except Exception as e:
        print(f"[STATUS]: Nenhuma fase global salva, usando padrao (0)")


# -----------FUNCOES PARA CONTROLE DE REGA INDIVIDUAL-----------#
def atualizar_dias_plantas():
    """Adiciona 1 dia para cada planta que ainda nao atingiu o limite"""
    for planta_id in range(1, 5):
        if plantas_rega[planta_id]["dias"] < 3:
            plantas_rega[planta_id]["dias"] += 1
            print(f"[STATUS]: Planta {planta_id} - Dias acumulados: {plantas_rega[planta_id]['dias']}/3")
    salvar_dados_rega()

def resetar_dias_planta(planta_id):
    """Reseta os dias acumulados de uma planta especifica (usado apos rega)"""
    if planta_id in plantas_rega:
        plantas_rega[planta_id]["dias"] = 0
        print(f"[CONTROL]: Planta {planta_id} - Dias resetados para 0")
        salvar_dados_rega()

def override_dias_planta(planta_id, novos_dias):
    """Sobrescreve os dias acumulados de uma planta via MQTT"""
    if planta_id in plantas_rega:
        if 0 <= novos_dias <= 3:
            plantas_rega[planta_id]["dias"] = novos_dias
            print(f"[MQTT]: Planta {planta_id} - Dias sobrescritos para {novos_dias}")
            salvar_dados_rega()
            return True
        else:
            print(f"[ERROR]: Valor invalido para dias: {novos_dias}. Use 0-3")
            return False
    return False

def pode_regar(planta_id):
    """Verifica se a planta pode ser regada (dias acumulados >= 3)"""
    return plantas_rega[planta_id]["dias"] >= 3


# -----------FUNCAO DE REGA-----------#
def executar_rega(planta_id, cycles, water_pump, plant_name=""):
    """Executa os ciclos de rega para uma planta"""
    total_cycles = cycles
    while cycles > 0:
        print(f"[CONTROL]: Planta {planta_id} - Ciclo {cycles} de {total_cycles}")
        water_pump(1)  # Turn pump ON
        sleep(10)  # Water for 10 seconds
        water_pump(0)  # Turn pump OFF
        if cycles > 1:
            sleep(10)  # Pause for 10 seconds between cycles
        cycles -= 1

def regar_planta(planta_id, water_pump, plant_name=""):
    """Rega a planta baseado na phase individual (quantidade de agua)"""
    state = plantas_rega[planta_id]["phase"]
    print(f"[CONTROL]: Regando {plant_name} - Fase de rega: {state}")

    # Determine watering cycles based on state
    if state == 0:
        cycles = 0
        print(f"[CONTROL]: Planta {planta_id} - Fase 0, sem rega necessaria")
    elif state == 1:
        cycles = 4  # 400ml
        print(f"[CONTROL]: Planta {planta_id} - Fase 1, aplicando 4 ciclos")
    elif state == 2:
        cycles = 8  # 800ml
        print(f"[CONTROL]: Planta {planta_id} - Fase 2, aplicando 8 ciclos")
    elif state == 3:
        cycles = 22  # 2.2L
        print(f"[CONTROL]: Planta {planta_id} - Fase 3, aplicando 22 ciclos")
    else:
        cycles = 0

    if cycles > 0:
        executar_rega(planta_id, cycles, water_pump, plant_name)
        resetar_dias_planta(planta_id)
        print(f"[CONTROL]: Planta {planta_id} - Rega concluida")
    else:
        print(f"[CONTROL]: Planta {planta_id} - Nenhum ciclo executado")

def verificar_e_regar_plantas():
    """Verifica todas as plantas e realiza a rega se necessario (dias >= 3)"""
    global rega_executada_hoje

    HOUR = ds.hour()

    # So executa rega quando as luzes estao apagadas (fora do horario de iluminacao)
    if hour_min <= HOUR < hour_max:
        # Dentro do horario de luz, nao pode regar
        return

    if rega_executada_hoje:
        return  # Ja regou hoje, nao faz nada

    print(f"[STATUS]: Verificando plantas para rega - Hora: {HOUR}")

    # Lista de plantas para regar
    plantas_para_regar = []
    for planta_id in range(1, 5):
        if pode_regar(planta_id):
            plantas_para_regar.append(planta_id)
            print(f"[STATUS]: Planta {planta_id} - Pronta para regar ({plantas_rega[planta_id]['dias']}/3 dias)")

    if len(plantas_para_regar) > 0:
        # Regar planta 1
        if 1 in plantas_para_regar:
            print(f"[CONTROL]: Planta 1 - Iniciando rega")
            regar_planta(1, io.water_pump_1, "Plant 1")
            sleep(30)

        # Regar planta 2
        if 2 in plantas_para_regar:
            print(f"[CONTROL]: Planta 2 - Iniciando rega")
            regar_planta(2, io.water_pump_2, "Plant 2")
            sleep(30)

        # Regar planta 3
        if 3 in plantas_para_regar:
            print(f"[CONTROL]: Planta 3 - Iniciando rega")
            regar_planta(3, io.water_pump_3, "Plant 3")
            sleep(30)

        # Regar planta 4
        if 4 in plantas_para_regar:
            print(f"[CONTROL]: Planta 4 - Iniciando rega")
            regar_planta(4, io.water_pump_4, "Plant 4")
            sleep(30)

        rega_executada_hoje = True
        salvar_dados_rega()  # Salva o estado de rega_executada_hoje
        print(f"[CONTROL]: Ciclo de rega finalizado")
    else:
        print(f"[STATUS]: Nenhuma planta precisa de rega no momento")


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
            print(f"[OK]: IP: {wlan.ifconfig()[0]}")
            print(f"[OK]: Signal: {wlan.status('rssi')} dBm")
            webrepl.start()
        else:
            print(f"[ERROR]: WiFi failed!")

    return wlan


# -----------MQTT CALLBACK (apenas armazena comandos)-----------#
def write_data(topic, message):
    """Callback MQTT - armazena comandos para processar depois"""
    topic = topic.decode('utf-8')
    value = message.decode('utf-8')
    comandos_recebidos.append((topic, value))
    print(f"[MQTT]: Comando recebido - Topic: {topic}, Value: {value}")


# -----------PROCESSAR COMANDOS RECEBIDOS-----------#
def processar_comandos_mqtt():
    """Processa todos os comandos recebidos durante o ciclo MQTT"""
    global plant_global_phase

    for topic, value in comandos_recebidos:
        # Fase Global
        if topic == 'plant_phase':
            try:
                nova_phase = int(value)
                if 0 <= nova_phase <= 3:
                    plant_global_phase = nova_phase
                    atualizar_parametros_globais()
                    salvar_fase_global()
                    print(f"[MQTT]: Fase global alterada para {nova_phase}")
                else:
                    print(f"[ERROR]: Phase invalida: {nova_phase}. Use 0-3")
            except Exception as e:
                print(f"[ERROR]: Erro ao processar fase global: {e}")

        # Fase individual (quantidade de agua) - worg/watering/plantX
        elif topic.startswith('worg/watering/'):
            try:
                planta_id = int(topic.split('/')[-1].replace('plant', ''))
                nova_phase = int(value)
                if 0 <= nova_phase <= 3:
                    if planta_id in plantas_rega:
                        plantas_rega[planta_id]["phase"] = nova_phase
                        print(f"[MQTT]: Planta {planta_id} - Fase de rega alterada para {nova_phase}")
                        salvar_dados_rega()
                else:
                    print(f"[ERROR]: Phase invalida: {nova_phase}. Use 0-3")
            except Exception as e:
                print(f"[ERROR]: Erro ao processar fase de rega: {e}")

        # Override de dias - worg/days/plantX
        elif topic.startswith('worg/days/'):
            try:
                planta_id = int(topic.split('/')[-1].replace('plant', ''))
                novos_dias = int(value)
                override_dias_planta(planta_id, novos_dias)
            except Exception as e:
                print(f"[ERROR]: Erro ao processar override: {e}")

    # Limpa a lista de comandos
    comandos_recebidos.clear()


# -----------FUNCAO MQTT: CONECTA, PUBLICA, RECEBE, DESCONECTA-----------#
def mqtt_ciclo():
    """Conecta no MQTT, publica dados, recebe comandos e desconecta"""
    client = None

    try:
        # Verifica se WiFi está conectado
        if not wlan.isconnected():
            print("[ERROR]: WiFi nao conectado, pulando MQTT")
            return

        # Cria e conecta cliente
        client = MQTTClient(MQTT_ID, server=MQTT_SERVER, port=MQTT_PORT,
                           user=MQTT_USER, password=MQTT_PASSWORD, keepalive=60)
        client.set_callback(write_data)
        client.connect()
        print("[OK]: MQTT conectado")

        # Inscreve nos topicos
        client.subscribe('plant_phase', qos=1)
        for planta_id in range(1, 5):
            client.subscribe(f'worg/watering/plant{planta_id}', qos=1)
            client.subscribe(f'worg/days/plant{planta_id}', qos=1)

        # Aguarda comandos por 2 segundos
        print("[MQTT]: Aguardando comandos...")
        start_wait = time.time()
        while time.time() - start_wait < 2:
            client.check_msg()
            sleep(0.1)

        # Processa comandos recebidos
        processar_comandos_mqtt()

        # Coleta dados dos sensores
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

        # Publica dados
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

        # Publica status dos componentes lendo diretamente dos pinos do MCP23017
        # Mantem os topicos originais worg/status/
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

        # Status das plantas
        for planta_id in range(1, 5):
            client.publish(f'worg/plant_status/{planta_id}',
                          f'{{"rega_phase": {plantas_rega[planta_id]["phase"]}, "dias": {plantas_rega[planta_id]["dias"]}}}',
                          qos=1)
        print("[OK]: MQTT plant status published")

    except Exception as e:
        print(f"[ERROR]: MQTT ciclo falhou: {e}")

    finally:
        if client:
            try:
                client.disconnect()
                print("[OK]: MQTT desconectado")
            except:
                pass


# -----------INICIALIZACAO-----------#
# Carregar dados salvos
carregar_fase_global()
carregar_dados_rega()
atualizar_parametros_globais()

# Conectar WiFi (mantém sempre conectado)
wlan = setup_wifi()

print("[STATUS]: Sistema iniciado")
sleep(10)

# -----------LOOP PRINCIPAL-----------#
while True:
    # Verifica e mantem WiFi conectado
    if not wlan.isconnected():
        print("[ERROR]: WiFi disconnected, reconnecting...")
        wlan = setup_wifi()
        if not wlan.isconnected():
            sleep(30)
            # Mesmo sem WiFi, o controle continua
        else:
            # WiFi reconectou, mas MQTT sera feito no proximo ciclo
            pass

    # Executa ciclo MQTT (conecta, publica, recebe, desconecta)
    # Se falhar, apenas pula - controle nao eh afetado
    mqtt_ciclo()

    # ========== CONTROLES LOCAIS (sempre executam) ==========
    try:
        # CONTROLE DE TEMPERATURA (ventiladores)
        temperatura = io.temp()

        if temperatura < 18:
            io.fan_1(0)
            io.fan_2(0)
            print("[CONTROL]: FAN 1:OFF, FAN 2:OFF")
        elif 18 <= temperatura < 22:
            io.fan_1(1)
            io.fan_2(0)
            print("[CONTROL]: FAN 1:ON, FAN 2:OFF")
        else:  # >= 22
            io.fan_1(1)
            io.fan_2(1)
            print("[CONTROL]: FAN 1:ON, FAN 2:ON")

        # CONTROLE DE VPD (umidificador/desumidificador)
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

        # CONTROLE DE ILUMINACAO
        HOUR = ds.hour()
        print(f"[STATUS]: Hour: {HOUR}")

        if hour_min <= HOUR < hour_max:
            io.lighting(0)
            print("[CONTROL]: Lightning: OFF")
        else:
            io.lighting(1)
            print("[CONTROL]: Lightning: ON")

        # ========== CONTROLE DE REGA (dias acumulados) ==========
        # Usando o dia do mes para detectar mudanca de dia
        try:
            dia_atual = ds.mday()
        except Exception as e:
            print(f"[ERROR]: get day: {e}")

        if ultimo_dia is None:
            ultimo_dia = dia_atual
            salvar_dados_rega()  # Salva imediatamente o ultimo_dia
            print(f"[STATUS]: Dia inicial registrado: {dia_atual}")
        elif dia_atual != ultimo_dia:
            print(f"[STATUS]: Novo dia detectado! {ultimo_dia} -> {dia_atual}")
            atualizar_dias_plantas()
            rega_executada_hoje = False
            ultimo_dia = dia_atual
            salvar_dados_rega()  # Salva apos mudanca de dia

        # Executar rega (se possivel)
        verificar_e_regar_plantas()

    except Exception as e:
        print(f"[ERROR]: Loop de controle: {e}")

    # Aguarda proximo ciclo
    print(f"[STATUS]: Aguardando {circle} segundos")
    sleep(circle)