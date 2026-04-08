from typing import List, Optional
from pydantic import BaseModel, Field
from domovoy.applications import AppBase
from domovoy.applications.registration import register_app

class TRVMapperConfig(BaseModel):
    climate_entity: str
    external_temp_input: str
    target_offset: float = 0.0  # e.g., +1 for main bedroom logic

class RoomClimateConfig(BaseModel):
    name: str
    temp_sensor: str
    update_interval_seconds: int
    trvs: List[TRVMapperConfig]

class HeatingConfig(BaseModel):
    heating_enabled_entity: str = "input_boolean.heating_enabled"
    heating_required_entity: str = "binary_sensor.heating_required"
    boiler_switch_entity: str = "switch.boiler_rt_switch"
    notify_target: str = "device/553b658b4ebcd80e8e58ba91a726fee3"
    
    boiler_return_temp_sensor: str = "sensor.ebusd_bai_returntemp_temp"
    boiler_target_temp_input: str = "input_number.boiler_desired_flow_temperature"
    mqtt_topic: str = "ebusd/bai/SetMode/set"
    boiler_update_interval_seconds: int = 600
    
    rooms: List[RoomClimateConfig] = []

class HeatingControlApp(AppBase[HeatingConfig]):
    async def initialize(self):
        self.log.info("Initializing Unified Heating Control App")
        
        # 1. Boiler State Callbacks
        self.callbacks.listen_state(
            entity_id=self.config.heating_enabled_entity,
            callback=self.check_heating_state
        )
        self.callbacks.listen_state(
            entity_id=self.config.heating_required_entity,
            callback=self.check_heating_state
        )

        # 2. Boiler Temperature MQTT Update
        self.callbacks.run_every(
            period=self.config.boiler_update_interval_seconds,
            callback=self.update_boiler_temp
        )

        # 3. TRV Updates per Room
        for room in self.config.rooms:
            # We use a closure or partial/default arg to bind the room to the callback
            self.callbacks.run_every(
                period=room.update_interval_seconds,
                callback=self.make_trv_updater(room)
            )

    async def check_heating_state(self, entity, old, new):
        heating_enabled = await self.hass.states.get(self.config.heating_enabled_entity)
        heating_required = await self.hass.states.get(self.config.heating_required_entity)
        boiler_switch = await self.hass.states.get(self.config.boiler_switch_entity)
        
        if not heating_enabled or not heating_required or not boiler_switch:
            return

        is_enabled = heating_enabled.state == "on"
        is_required = heating_required.state == "on"
        is_boiler_on = boiler_switch.state == "on"

        if is_enabled and is_required and not is_boiler_on:
            self.log.info("Heating enabled & required. Turning boiler ON.")
            await self.hass.services.call("switch", "turn_on", {"entity_id": self.config.boiler_switch_entity})
            await self.hass.services.call("notify", "send_message", {
                "message": "🌡️Boiler turned on",
                "target": [self.config.notify_target]
            })
        elif (not is_enabled or not is_required) and is_boiler_on:
            self.log.info("Heating not required/enabled. Turning boiler OFF.")
            await self.hass.services.call("switch", "turn_off", {"entity_id": self.config.boiler_switch_entity})
            await self.hass.services.call("notify", "send_message", {
                "message": "🌡️Boiler turned off",
                "target": [self.config.notify_target]
            })

    async def update_boiler_temp(self, kwargs):
        heating_enabled = await self.hass.states.get(self.config.heating_enabled_entity)
        heating_required = await self.hass.states.get(self.config.heating_required_entity)
        
        if not heating_enabled or heating_enabled.state != "on": return
        if not heating_required or heating_required.state != "on": return
            
        return_temp_state = await self.hass.states.get(self.config.boiler_return_temp_sensor)
        desired_temp_state = await self.hass.states.get(self.config.boiler_target_temp_input)
        
        if not return_temp_state or not desired_temp_state: return
            
        try:
            ret_temp = float(return_temp_state.state)
            desired_temp = float(desired_temp_state.state)
        except ValueError:
            return
            
        if ret_temp + 3 < desired_temp:
            payload = f"auto;{desired_temp};-;-;0;0;0;0;0;0"
            self.log.info(f"Setting boiler temp: {payload}")
            await self.hass.services.call("mqtt", "publish", {
                "topic": self.config.mqtt_topic,
                "payload": payload,
                "qos": "1",
                "retain": True
            })

    def make_trv_updater(self, room: RoomClimateConfig):
        async def updater(kwargs):
            heating_enabled = await self.hass.states.get(self.config.heating_enabled_entity)
            if not heating_enabled or heating_enabled.state != "on":
                return

            room_sensor = await self.hass.states.get(room.temp_sensor)
            if not room_sensor: return
            try:
                room_temp = float(room_sensor.state)
            except ValueError: return

            for trv in room.trvs:
                climate = await self.hass.states.get(trv.climate_entity)
                if not climate: continue
                
                target_temp = float(climate.attributes.get("temperature", 0))
                # Evaluate condition: target > room_temp + offset (e.g. +1 for main bed)
                if target_temp > (room_temp + trv.target_offset):
                    await self.hass.services.call("number", "set_value", {
                        "entity_id": trv.external_temp_input,
                        "value": room_temp
                    })
        return updater


# --- Configuration Instances ---
default_rooms = [
    RoomClimateConfig(
        name="Living Room",
        temp_sensor="sensor.living_room_t1_temperature",
        update_interval_seconds=300,
        trvs=[
            TRVMapperConfig(
                climate_entity="climate.trv_dining_table",
                external_temp_input="number.trv_dining_table_external_measured_room_sensor"
            ),
            TRVMapperConfig(
                climate_entity="climate.living_room_window_trv",
                external_temp_input="number.living_room_window_trv_external_temperature_input"
            )
        ]
    ),
    RoomClimateConfig(
        name="Main Bedroom",
        temp_sensor="sensor.bedroom_t1_temperature",
        update_interval_seconds=1800,
        trvs=[
            TRVMapperConfig(
                climate_entity="climate.main_bedroom",
                external_temp_input="number.main_bedroom_external_temperature_input",
                target_offset=1.0  # Replicates the `value_template: '{{ value + 1 }}'` logic
            )
        ]
    ),
    RoomClimateConfig(
        name="Office",
        temp_sensor="sensor.office_t1_temperature",
        update_interval_seconds=1800,
        trvs=[
            TRVMapperConfig(
                climate_entity="climate.office_trv",
                external_temp_input="number.office_trv_external_temperature_input"
            )
        ]
    )
]

register_app(
    app_class=HeatingControlApp,
    app_name="home_heating_control",
    config=HeatingConfig(rooms=default_rooms)
)
