from pydantic import BaseModel
from domovoy.applications import AppBase
from domovoy.applications.registration import register_app

class DoorbellConfig(BaseModel):
    virtual_relay: str
    notification_message: str = "Someone is at the door!"
    media_players: list[str] = []

class DoorbellApp(AppBase[DoorbellConfig]):
    async def initialize(self):
        self.log.info(f"Initializing Doorbell Interception App for {self.config.virtual_relay}")
        
        # Listen for the virtual doorbell relay turning ON
        self.callbacks.listen_state(
            entity_id=self.config.virtual_relay,
            callback=self.on_doorbell_press,
            new="on"
        )

    async def on_doorbell_press(self, entity_id, old, new):
        self.log.info("Doorbell relay triggered! Sending notifications.")
        
        # Notify mobile devices via Home Assistant notify service
        await self.hass.services.call(
            "notify", "notify", 
            {"message": self.config.notification_message, "title": "Doorbell"}
        )
        
        # Announce on media players if configured
        for player in self.config.media_players:
            await self.hass.services.call(
                "tts", "google_translate_say",
                {"entity_id": player, "message": self.config.notification_message}
            )
            
        # Reset the virtual relay back to off so it can be triggered again
        await self.hass.services.call("input_boolean", "turn_off", {"entity_id": self.config.virtual_relay})

register_app(
    app_class=DoorbellApp,
    app_name="tapo_doorbell_interception",
    config=DoorbellConfig(
        virtual_relay="input_boolean.virtual_doorbell_relay",
        notification_message="Ding dong! Someone is at the front door.",
        media_players=["media_player.living_room_speaker", "media_player.kitchen_speaker"]
    ),
)
