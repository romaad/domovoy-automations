from domovoy.applications import AppBase
from domovoy.applications.registration import register_app

class BoilerControlApp(AppBase):
    async def initialize(self):
        self.log.info("Initializing Boiler Control App")
        
        # Turn boiler on when heating is required
        self.callbacks.listen_state(
            entity_id="input_boolean.heating_enabled",
            callback=self.check_heating_state
        )
        self.callbacks.listen_state(
            entity_id="binary_sensor.heating_required",
            callback=self.check_heating_state
        )

        # Set boiler flow temp via MQTT periodically
        self.callbacks.run_every(
            period=600, # every 10 minutes
            callback=self.update_boiler_temp
        )

    async def check_heating_state(self, entity, old, new):
        heating_enabled = await self.hass.states.get("input_boolean.heating_enabled")
        heating_required = await self.hass.states.get("binary_sensor.heating_required")
        boiler_switch = await self.hass.states.get("switch.boiler_rt_switch")
        
        if not heating_enabled or not heating_required or not boiler_switch:
            return

        is_enabled = heating_enabled.state == "on"
        is_required = heating_required.state == "on"
        is_boiler_on = boiler_switch.state == "on"

        if is_enabled and is_required and not is_boiler_on:
            self.log.info("Heating enabled and required. Turning boiler ON.")
            await self.hass.services.call("switch", "turn_on", {"entity_id": "switch.boiler_rt_switch"})
            await self.hass.services.call("notify", "send_message", {
                "message": "🌡️Boiler turned on",
                "target": ["device/553b658b4ebcd80e8e58ba91a726fee3"]
            })
        elif (not is_enabled or not is_required) and is_boiler_on:
            self.log.info("Heating not required/enabled. Turning boiler OFF.")
            await self.hass.services.call("switch", "turn_off", {"entity_id": "switch.boiler_rt_switch"})
            await self.hass.services.call("notify", "send_message", {
                "message": "🌡️Boiler turned off",
                "target": ["device/553b658b4ebcd80e8e58ba91a726fee3"]
            })

    async def update_boiler_temp(self, kwargs):
        heating_enabled = await self.hass.states.get("input_boolean.heating_enabled")
        heating_required = await self.hass.states.get("binary_sensor.heating_required")
        
        if not heating_enabled or heating_enabled.state != "on":
            return
        if not heating_required or heating_required.state != "on":
            return
            
        return_temp_state = await self.hass.states.get("sensor.ebusd_bai_returntemp_temp")
        desired_temp_state = await self.hass.states.get("input_number.boiler_desired_flow_temperature")
        
        if not return_temp_state or not desired_temp_state:
            return
            
        try:
            ret_temp = float(return_temp_state.state)
            desired_temp = float(desired_temp_state.state)
        except ValueError:
            return
            
        if ret_temp + 3 < desired_temp:
            payload = f"auto;{desired_temp};-;-;0;0;0;0;0;0"
            self.log.info(f"Setting boiler temp: {payload}")
            await self.hass.services.call("mqtt", "publish", {
                "topic": "ebusd/bai/SetMode/set",
                "payload": payload,
                "qos": "1",
                "retain": True
            })

register_app(app_class=BoilerControlApp, app_name="boiler_control")
