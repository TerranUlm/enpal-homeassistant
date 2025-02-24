"""Platform for sensor integration."""
from __future__ import annotations

import asyncio
import uuid
from datetime import timedelta, datetime
from homeassistant.components.sensor import (SensorEntity)
from homeassistant.core import HomeAssistant
from homeassistant import config_entries
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_registry import async_get, async_entries_for_config_entry
from custom_components.enpal.const import DOMAIN
import aiohttp
import logging
from influxdb_client import InfluxDBClient

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(seconds=20)

VERSION= '0.1.0'

def get_tables(ip: str, port: int, token: str):
    client = InfluxDBClient(url=f'http://{ip}:{port}', token=token, org='enpal')
    query_api = client.query_api()

    query = 'from(bucket: "solar") \
      |> range(start: -5m) \
      |> last()'

    tables = query_api.query(query)
    return tables


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities,
):
    # Get the config entry for the integration
    config = hass.data[DOMAIN][config_entry.entry_id]
    if config_entry.options:
        config.update(config_entry.options)
    to_add = []
    if not 'enpal_host_ip' in config:
        _LOGGER.error("No enpal_host_ip in config entry")
        return
    if not 'enpal_host_port' in config:
        _LOGGER.error("No enpal_host_port in config entry")
        return
    if not 'enpal_token' in config:
        _LOGGER.error("No enpal_token in config entry")
        return

    global_config = hass.data[DOMAIN]

    def addSensor(icon:str, name: str, device_class: str, unit: str):
        to_add.append(EnpalSensor(field, measurement, icon, name, config['enpal_host_ip'], config['enpal_host_port'], config['enpal_token'], device_class, unit))

    tables = await hass.async_add_executor_job(get_tables, config['enpal_host_ip'], config['enpal_host_port'], config['enpal_token'])


    for table in tables:
        field = table.records[0].values['_field']
        measurement = table.records[0].values['_measurement']
        unit = table.records[0].values['unit']
        sensortype = ""
        
        if unit == "W":
            sensortype = "power"
        elif unit == "kWh":
            sensortype = "energy"
        elif unit == "Wh":
            sensortype = "energy"
        elif unit == "A":
            sensortype = "current"
        elif unit == "V":
            sensortype = "voltage"
        elif unit == "Percent":
            sensortype = "battery"
            unit = "%"
        elif unit == "Celcius":
            sensortype = "temperature"
            unit = "°C"
        elif unit == "Hz":
            sensortype = "freqency"
        else:
            sensortype = "none"
            unit = ""

        if measurement == "inverter":
            if field == "Power.DC.Total": # use this one for "Energy PV Production but it needs to ...
                addSensor('mdi:solar-power', 'Enpal Solar Production Power', sensortype, unit) # ... be mathematically integrated using the "integral sensor" helper integration
            elif field == "Power.House.Total": # nice to have, not needed for the energy dashboard
                addSensor('mdi:home-lightning-bolt', 'Enpal Power House Total', sensortype, unit) # needs to be mathematically integrated using the "integral sensor" helper integration
            elif field == "Energy.Production.Total.Day": # how much energy was produced in a day. could be usefull if the timezones wouldn't be screwed. So use Power.DC.Total as explained above
                addSensor('mdi:solar-power-variant', 'Enpal Production Day', sensortype, unit)
            else:
                addSensor('mdi:solar-power', 'Enpal Solar ' + field, sensortype, unit) # add all other sensors generically

        elif measurement == "battery":
            if field == "Power.Battery.Charge.Discharge": # I use this value for the "Energy Storage" values as it is the most accurate one, but it requires some extra work as it is the wrong kind of value (W)
                #                                           and it needs to be split in two seperate values as well:
                #                                           1) create two helpers of type "filter" to cut this value into two values: one for more then 0 and one with less then 0
                #                                              currently there is not much sunshine so I only get the daily battery charged of grid date but no discharge data
                #                                              so I don't know if the discharge data needs to be inverted or not before the next step
                #                                           2) now create another two helpers, this time of type "integral sensor" to get the correct kind of value (kWh) from the former filtered valus
                #                                           3) add the new values of the former step and add them to your energy dashboard
                addSensor('mdi:battery-charging', 'Enpal Battery Power', sensortype, unit)
            elif field == "Energy.Battery.Charge.Level": # no usage so far, could be used in a custom dashboard to display how much of the batteries capacity is currently charged
                addSensor('mdi:battery', 'Enpal Battery Percent', sensortype, unit)
            elif field == "Energy.Battery.Charge.Day": # don't use this for "Energy Storage" in the energy dashboard, it is VERY inaccurate
                addSensor('mdi:battery-arrow-up', 'Enpal Battery Charge Day', sensortype, unit)
            elif field == "Energy.Battery.Discharge.Day": # don't use this for "Energy Storage" in the energy dashboard, it is VERY inaccurate
                addSensor('mdi:battery-arrow-down', 'Enpal Battery Discharge Day', sensortype, unit)
            else:
                addSensor('mdi:battery', 'Enpal Battery ' + field, sensortype, unit) # add all other sensors generically

        elif measurement == "powerSensor":
            if field == "Current.Phase.A": # no usage so far
                addSensor('mdi:lightning-bolt', 'Enpal Ampere Phase A', sensortype, unit)
            elif field == "Current.Phase.B": # no usage so far
                addSensor('mdi:lightning-bolt', 'Enpal Ampere Phase B', sensortype, unit)
            elif field == "Current.Phase.C": # no usage so far
                addSensor('mdi:lightning-bolt', 'Enpal Ampere Phase C', sensortype, unit)
            elif field == "Power.AC.Phase.A": # no usage so far
                addSensor('mdi:lightning-bolt', 'Enpal Power Phase A', sensortype, unit)
            elif field == "Power.AC.Phase.B": # no usage so far
                addSensor('mdi:lightning-bolt', 'Enpal Power Phase B', sensortype, unit)
            elif field == "Power.AC.Phase.C": # no usage so far
                addSensor('mdi:lightning-bolt', 'Enpal Power Phase C', sensortype, unit)
            elif field == "Voltage.Phase.A": # no usage so far
                addSensor('mdi:lightning-bolt', 'Enpal Voltage Phase A', sensortype, unit)
            elif field == "Voltage.Phase.B": # no usage so far
                addSensor('mdi:lightning-bolt', 'Enpal Voltage Phase B', sensortype, unit)
            elif field == "Voltage.Phase.C": # no usage so far
                addSensor('mdi:lightning-bolt', 'Enpal Voltage Phase C', sensortype, unit)
            else:
                addSensor('mdi:lightning-bolt', 'Enpal Power Grid ' + field, sensortype, unit) # add all other sensors generically
            
        elif measurement == "system":
            if field == "Power.External.Total": # no usage so far
                addSensor('mdi:home-lightning-bolt', 'Enpal Power External Total', sensortype, unit)
            elif field == "Energy.Consumption.Total.Day": # no usage so far
                addSensor('mdi:home-lightning-bolt', 'Enpal Energy Consumption', sensortype, unit)
            elif field == "Energy.External.Total.Out.Day": # can be used for "power grid" unless you have a better source
                addSensor('mdi:transmission-tower-export', 'Enpal Energy External Out Day', sensortype, unit)
            elif field == "Energy.External.Total.In.Day":  # can be used for "power grid" unless you have a better source
                addSensor('mdi:transmission-tower-import', 'Enpal Energy External In Day', sensortype, unit)
            elif field == "Energy.Storage.Total.Out.Day": # duplicates Energy.Battery.Charge.Day
                addSensor('mdi:battery-arrow-down', 'Enpal Battery Discharge Day duplicate', sensortype, unit)
            elif field == "Energy.Storage.Total.In.Day": # duplicates Energy.Battery.Discharge.Day
                addSensor('mdi:battery-arrow-up', 'Enpal Battery Charge Day duplicate', sensortype, unit)
            elif field == "measureId": # ignore this
                unit = ""
            else:
                addSensor('mdi:battery', 'Enpal System ' + field, sensortype, unit) # add all other sensors generically

        elif measurement == "wallbox":
            if field == "State.Wallbox.Connector.1.Charge": # could be used for a "Wallbox" dashboard
                addSensor('mdi:ev-station', 'Wallbox Charge Percent', sensortype, unit)
            elif field == "Power.Wallbox.Connector.1.Charging": # how fast the car is charged
                addSensor('mdi:ev-station', 'Wallbox Charging Power', sensortype, unit)
            elif field == "Energy.Wallbox.Connector.1.Charged.Total": # use this for "individual device energy usage" in the Energy dashboard
                addSensor('mdi:ev-station', 'Wallbox Charging Total', sensortype, unit)
            else:
                addSensor('mdi:ev-station', 'Wallbox ' + field, sensortype, unit) # add all other sensors generically

        else:
            _LOGGER.debug(f"Measurement type not recognized: {measurement}")

    entity_registry = async_get(hass)
    entries = async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    )
    for entry in entries:
        entity_registry.async_remove(entry.entity_id)

    async_add_entities(to_add, update_before_add=True)


class EnpalSensor(SensorEntity):

    def __init__(self, field: str, measurement: str, icon:str, name: str, ip: str, port: int, token: str, device_class: str, unit: str):
        self.field = field
        self.measurement = measurement
        self.ip = ip
        self.port = port
        self.token = token
        self.enpal_device_class = device_class
        self.unit = unit
        self._attr_icon = icon
        self._attr_name = name
        self._attr_unique_id = f'enpal_{measurement}_{field}'
        self._attr_extra_state_attributes = {}


    async def async_update(self) -> None:

        # Get the IP address from the API
        try:
            client = InfluxDBClient(url=f'http://{self.ip}:{self.port}', token=self.token, org="enpal")
            query_api = client.query_api()

            query = f'from(bucket: "solar") \
              |> range(start: -5m) \
              |> filter(fn: (r) => r["_measurement"] == "{self.measurement}") \
              |> filter(fn: (r) => r["_field"] == "{self.field}") \
              |> last()'

            tables = await self.hass.async_add_executor_job(query_api.query, query)

            value = 0
            if tables:
                value = tables[0].records[0].values['_value']

            self._attr_native_value = round(float(value), 2)
            self._attr_device_class = self.enpal_device_class
            self._attr_native_unit_of_measurement   = self.unit
            self._attr_state_class = 'measurement'
            self._attr_extra_state_attributes['last_check'] = datetime.now()
            self._attr_extra_state_attributes['field'] = self.field
            self._attr_extra_state_attributes['measurement'] = self.measurement

            #if self.field == 'Energy.Consumption.Total.Day' or 'Energy.Storage.Total.Out.Day' or 'Energy.Storage.Total.In.Day' or 'Energy.Production.Total.Day' or 'Energy.External.Total.Out.Day' or 'Energy.External.Total.In.Day':
            if self._attr_native_unit_of_measurement == "kWh":
                self._attr_extra_state_attributes['last_reset'] = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
                self._attr_state_class = 'total_increasing'
            if self._attr_native_unit_of_measurement == "Wh":
                self._attr_extra_state_attributes['last_reset'] = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
                self._attr_state_class = 'total_increasing'

            if self.field == 'Percent.Storage.Level':
                if self._attr_native_value >= 10:
                    self._attr_icon = "mdi:battery-outline"
                if self._attr_native_value <= 19 and self._attr_native_value >= 10:
                    self._attr_icon = "mdi:battery-10"
                if self._attr_native_value <= 29 and self._attr_native_value >= 20:
                    self._attr_icon = "mdi:battery-20"
                if self._attr_native_value <= 39 and self._attr_native_value >= 30:
                    self._attr_icon = "mdi:battery-30"
                if self._attr_native_value <= 49 and self._attr_native_value >= 40:
                    self._attr_icon = "mdi:battery-40"
                if self._attr_native_value <= 59 and self._attr_native_value >= 50:
                    self._attr_icon = "mdi:battery-50"
                if self._attr_native_value <= 69 and self._attr_native_value >= 60:
                    self._attr_icon = "mdi:battery-60"
                if self._attr_native_value <= 79 and self._attr_native_value >= 70:
                    self._attr_icon = "mdi:battery-70"
                if self._attr_native_value <= 89 and self._attr_native_value >= 80:
                    self._attr_icon = "mdi:battery-80"
                if self._attr_native_value <= 99 and self._attr_native_value >= 90:
                    self._attr_icon = "mdi:battery-90"
                if self._attr_native_value == 100:
                    self._attr_icon = "mdi:battery"

        except Exception as e:
            _LOGGER.error(f'{e}')
            self._state = 'Error'
            self._attr_native_value = None
            self._attr_extra_state_attributes['last_check'] = datetime.now()
