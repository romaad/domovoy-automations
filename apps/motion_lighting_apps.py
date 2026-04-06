from typing import List
from pydantic import BaseModel
from domovoy.applications import AppBase
from domovoy.applications.registration import register_app

class MotionLightConfig(BaseModel):
    motion_sensors: List[str]
    lights: List[str]
    timeout_minutes: int = 5

class MotionLightApp(AppBase[MotionLightConfig]):
    async def initialize(self):
        self.log.info(f"Initializing generic motion lighting for {self.config.lights}")
        
        # Listen for motion
        for sensor in self.config.motion_sensors:
            self.callbacks.listen_state(
                entity_id=sensor,
                callback=self.on_motion,
                new="on"
            )
            # Listen for motion cleared
            self.callbacks.listen_state(
                entity_id=sensor,
                callback=self.on_motion_clear,
                new="off",
                duration=self.config.timeout_minutes * 60
            )

    async def on_motion(self, entity_id, old, new):
        self.log.info(f"Motion detected by {entity_id}")
        for light in self.config.lights:
            await self.hass.services.call("light", "turn_on", {"entity_id": light})

    async def on_motion_clear(self, entity_id, old, new):
        self.log.info(f"Motion cleared on {entity_id} for {self.config.timeout_minutes} mins")
        for light in self.config.lights:
            await self.hass.services.call("light", "turn_off", {"entity_id": light})

# Example Instantiation (Configurable via external means or below)
register_app(
    app_class=MotionLightApp,
    app_name="living_room_motion_lights",
    config=MotionLightConfig(
        motion_sensors=["binary_sensor.living_room_motion"],
        lights=["light.living_room_main"],
        timeout_minutes=10
    ),
)