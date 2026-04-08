import os
import csv
from datetime import datetime, timedelta
from pydantic import BaseModel
from domovoy.applications import AppBase
from domovoy.applications.registration import register_app

class EnergyTrackingConfig(BaseModel):
    tracked_entities: dict[str, str]  # friendly_name -> entity_id
    output_file: str = "/home/ramadan/.openclaw/workspace/metrics/daily_energy.csv"

class EnergyTrackingApp(AppBase[EnergyTrackingConfig]):
    async def initialize(self):
        self.log.info("Initializing Daily Energy Tracking App")
        
        # Schedule to run every day at 00:01
        self.callbacks.run_daily(
            time="00:01:00",
            callback=self.record_daily_energy
        )

    async def record_daily_energy(self, kwargs):
        self.log.info("Fetching HA energy data for the previous 24 hours")
        today = datetime.now()
        yesterday_str = (today - timedelta(days=1)).strftime("%Y-%m-%d")
        
        row = {"date": yesterday_str}
        
        for name, entity_id in self.config.tracked_entities.items():
            state = await self.hass.states.get(entity_id)
            if state:
                # Store the state (assumes it's an accumulating sensor or we calculate it here)
                row[name] = state.state
            else:
                row[name] = "0.0"
                
        # Ensure directory exists
        os.makedirs(os.path.dirname(self.config.output_file), exist_ok=True)
        
        file_exists = os.path.isfile(self.config.output_file)
        
        with open(self.config.output_file, "a", newline="") as csvfile:
            fieldnames = ["date"] + list(self.config.tracked_entities.keys())
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            if not file_exists:
                writer.writeheader()
                
            writer.writerow(row)
            
        self.log.info(f"Energy data appended to {self.config.output_file}")

register_app(
    app_class=EnergyTrackingApp,
    app_name="daily_energy_tracker",
    config=EnergyTrackingConfig(
        tracked_entities={
            "boiler_demand": "sensor.boiler_energy_daily",
            "burner_heating": "sensor.burner_heating_daily",
            "refrigerator": "sensor.refrigerator_energy_daily",
            "washer_dishwasher": "sensor.washer_dishwasher_energy_daily"
        }
    ),
)
