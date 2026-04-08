from domovoy.applications import AppBase
from domovoy.applications.registration import register_app

class DoorNotificationsApp(AppBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.doors = [
            "binary_sensor.0xa4c138962308f00b_contact",
            "binary_sensor.garden_door_contact",
            "binary_sensor.garden_patio_door_contact"
        ]

    async def initialize(self):
        self.log.info("Initializing Door Notifications App")
        for door in self.doors:
            self.callbacks.listen_state(
                entity_id=door,
                callback=self.on_door_state_change
            )
            # Listen for open for 20 minutes
            self.callbacks.listen_state(
                entity_id=door,
                new="on",
                duration=20 * 60,
                callback=self.on_door_open_too_long
            )

    async def on_door_state_change(self, entity, old, new):
        if old == new: return
        state_obj = await self.hass.states.get(entity)
        friendly_name = state_obj.attributes.get("friendly_name", entity)
        
        status = "opened" if new == "on" else "closed"
        emoji = "🚪"
        
        # Send text notification
        await self.hass.services.call("notify", "notify", {"message": f"{friendly_name} was {status}"})
        
        # Take snapshot
        snapshot_file = f"/media/{entity}/door_{status}_snapshot.jpg"
        await self.hass.services.call("camera", "snapshot", {
            "entity_id": ["camera.front_door", "camera.garden"],
            "filename": snapshot_file
        })
        
        # Send Telegram Photo
        await self.hass.services.call("telegram_bot", "send_photo", {
            "target": ["-5210499759"],
            "file": snapshot_file,
            "caption": f"{emoji} {friendly_name} was {status}",
            "verify_ssl": True
        })

    async def on_door_open_too_long(self, entity, old, new):
        state_obj = await self.hass.states.get(entity)
        friendly_name = state_obj.attributes.get("friendly_name", entity)
        
        msg = f"{friendly_name} is left open for 20 minutes"
        self.log.info(msg)
        
        await self.hass.services.call("notify", "notify", {"message": msg})
        await self.hass.services.call("notify", "send_message", {
            "message": msg,
            "target": ["device/553b658b4ebcd80e8e58ba91a726fee3"]
        })

register_app(app_class=DoorNotificationsApp, app_name="door_notifications")
