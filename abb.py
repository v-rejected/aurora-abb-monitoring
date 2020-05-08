from influxdb import InfluxDBClient
from aurorapy.client import AuroraError, AuroraSerialClient
from astral import LocationInfo
from astral.sun import sun
import datetime
import yaml
import os
import sys
import time

def load_config(config_file):
    path = os.path.join(script_dir, config_file)
    try:
        with open(path, 'r') as config:
            return yaml.safe_load(config)
    except Exception as error:
        print('error')
    sys.exit(1)

script_dir = os.path.dirname(os.path.abspath(__file__))
cfg = load_config('config.yml')

def crate_json(measurement, tag, obj):
    output = []
    for key in obj:
        influxItem = {}
        influxItem['measurement'] = measurement
        influxItem['tags'] = {tag: key}
        influxItem['time'] = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
        influxItem['fields'] = {'value': obj[key]}
        output.append(influxItem)
    return output

def AuroraRetry(connection ):
    retry = True
    morning = False
    retryCount = 0
    while retry:
        try:
            connection = ABBAuroraMonitoring(cfg)
            return connection
        except AuroraError as error:
            print('still error')
        retryCount +=1
        if retryCount > 5:
            retry = False
        time.sleep(5)
    city = LocationInfo(conf['location']['city'], conf['location']['country'], conf['location']['citime_zonety'], conf['location']['N'], conf['location']['E'])
    s = sun(city.observer, date=datetime.datetime.utcnow().date())
    if datetime.datetime.utcnow() > s["sunset"]:
        s = sun(city.observer, date=datetime.datetime.utcnow().date()) + datetime.timedelta(days=1)
    else:
        print('error')
        sys.exit(10)
    while not morning:
        if datetime.datetime.utcnow() < s["sunrise"]:
            time.sleep(300)
        elif datetime.datetime.utcnow() >= s["sunrise"]:
            morning = True
        else:
            print('something whent wrong')
            sys.exit(9)
    retry = True
    while retry:
        try:
            connection = ABBAuroraMonitoring(cfg)
            return connection
        except AuroraError as error:
            print('still error')
        retryCount +=1
        if retryCount > 5:
            retry = False
        time.sleep(5)

class ABBAuroraMonitoring ():

    def __init__(self, config):
        self.clientABB = AuroraSerialClient(config['aurora']['address'], config['aurora']['com_port'], parity="N", timeout=1)
        self.clientABB.connect()
        self.state()
        self.temperature()
        self.cumulated()
        self.monitoring()

    def close(self):
        self.clientABB.close()

    def state(self):
        obj = {}
        obj['global_state'] = (self.clientABB.state(1))
        obj['alarm'] = (self.clientABB.state(5))
        self.status = obj

    def temperature(self):
        obj = {}
        obj['inverter'] = round(self.clientABB.measure(21),1)        
        obj['booster'] = round(self.clientABB.measure(22),1)
        self.temp = obj

    def cumulated(self):
        obj = {}
        obj['curent_day'] = round(self.clientABB.cumulated_energy(0),1)
        obj['week'] = round(self.clientABB.cumulated_energy(1),1)        
        obj['month'] = round(self.clientABB.cumulated_energy(4),1)        
        obj['total'] = round(self.clientABB.cumulated_energy(6),1)
        self.cumulated_energy = obj
    
    def monitoring(self):
        obj = {}
        obj['grid_voltage'] = round(self.clientABB.measure(1),1)
        obj['grid_power'] = round(self.clientABB.measure(3, True),1)
        obj['vbulk'] = round(self.clientABB.measure(5),1)
        obj['leak_dc'] = round(self.clientABB.measure(6),1)
        obj['leak_Inverter'] = round(self.clientABB.measure(7),1)
        obj['power_peak'] = round(self.clientABB.measure(35),1)
        self.monitoring_status = obj

class WriteToInfluxDB():

    def __init__(self, config):
        self.clientDB = InfluxDBClient(config['influxdb']['host'], config['influxdb']['port'], config['influxdb']['user'], config['influxdb']['password'], config['influxdb']['db_name'])
        self.cratedb(config)

    def cratedb(self, config):
        dblist = self.clientDB.get_list_database()
        exist = False
        for db in dblist:
            if db["name"] == (config['influxdb']['db_name']):
                exist = True
        if not exist:
            self.clientDB.create_database(config['influxdb']['db_name'])

    def writedb(self, json_body):
        self.clientDB.write_points(json_body)

if __name__ == '__main__':
    
    connection = ABBAuroraMonitoring(cfg)
    connect = WriteToInfluxDB(cfg)
    while True:
        try:
            obj = []
            timenow = datetime.datetime.utcnow()
            connection.temperature()
            connection.monitoring()
            obj += crate_json('temperature', 'sensor', connection.temp)
            obj += crate_json('monitoring', 'sensor', connection.monitoring_status)
            if timenow.second in [0, 10, 20, 30, 40, 50]:
                connection.cumulated()
                obj += crate_json('cumulated', 'timeframe', connection.cumulated_energy)
            if timenow.second == 0:
                connection.state()
                obj += crate_json('state', 'timeframe', connection.status)
            connect.writedb(obj)
            time.sleep(1)
        except AuroraError as error:
            print('ERROR: {}'.format(error))
            connection = AuroraRetry(connection)