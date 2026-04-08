from domovoy.applications import AppBase
from domovoy.applications.registration import register_app

class TRVUpdateApp(AppBase):
    async def initialize(self):
        self.log.info("Initializing TRV Update App")
        
        # Run every 5 minutes for Living Room
        self.callbacks.run_every(period=300, callback=self.update_living_room_trv)
        
        # Run every 30 minutes for Main Bed & Office
        self.callbacks.run_every(period=1800, callback=self.update_bedroom_office_trvs)

    async def update_living_room_trv(self, kwargs):
        heating_enabled = await self.hass.states.get("input_boolean.heating_enabled")
        if not heating_enabled or heating_enabled.state != "on":
            return

        lr_temp_sensor = await self.hass.states.get("sensor.living_room_t1_temperature")
        if not lr_temp_sensor: return
        try:
            lr_temp = float(lr_temp_sensor.state)
        except ValueError: return

        trv_dining = await self.hass.states.get("climate.trv_dining_table")
        trv_window = await self.hass.states.get("climate.living_room_window_trv")
        
        needs_update = False
        if trv_dining and float(trv_dining.attributes.get("temperature", 0)) > lr_temp:
            needs_update = True
        if trv_window and float(trv_window.attributes.get("temperature", 0)) > lr_temp:
            needs_update = True

        if needs_update:
            await self.hass.services.call("number", "set_value", {
                "entity_id": "number.trv_dining_table_external_measured_room_sensor",
                "value": lr_temp
            })
            await self.hass.services.call("number", "set_value", {
                "entity_id": "number.living_room_window_trv_external_temperature_input",
                "value": lr_temp
            })

    async def update_bedroom_office_trvs(self, kwargs):
        heating_enabled = await self.hass.states.get("input_boolean.heating_enabled")
        if not heating_enabled or heating_enabled.state != "on":
            return

        # Main Bedroom
        bed_sensor = await self.hass.states.get("sensor.bedroom_t1_temperature")
        lr_sensor = await self.hass.states.get("sensor.living_room_t1_temperature")
        climate_bed = await self.hass.states.get("climate.main_bedroom")
        
        if bed_sensor and lr_sensor and climate_bed:
            try:
                bed_temp = float(bed_sensor.state)
                lr_temp = float(lr_sensor.state)
                bed_target = float(climate_bed.attributes.get("temperature", 0))
                
                if bed_target > (bed_temp + 1):
                    await self.hass.services.call("number", "set_value", {
                        "entity_id": "number.main_bedroom_external_temperature_input",
                        "value": lr_temp
                    })
            except ValueError:
                pass

        # Office
        office_sensor = await self.hass.states.get("sensor.office_t1_temperature")
        climate_office = await self.hass.states.get("climate.office_trv")
        
        if office_sensor and climate_office:
            try:
                office_temp = float(office_sensor.state)
                office_target = float(climate_office.attributes.get("temperature", 0))
                
                if office_target > office_temp:
                    await self.hass.services.call("number", "set_value", {
                        "entity_id": "number.office_trv_external_temperature_input",
                        "value": office_temp
                    })
            except ValueError:
                pass

register_app(app_class=TRVUpdateApp, app_name="trv_updates")
