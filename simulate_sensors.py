"""
Real-time IoT Sensor Simulator
Automatically generates and submits sensor readings to simulate real sensors
"""

import asyncio
import random
import time
from datetime import datetime
import requests
from typing import List, Dict

# Configuration
BACKEND_URL = "http://localhost:8000"
BATCH_IDS = ["BATCH-001", "BATCH-002", "BATCH-003"]  # Batches to monitor
SENSORS = [
    {"id": "SENSOR-T-001", "type": "transporter", "batch": "BATCH-001"},
    {"id": "SENSOR-T-002", "type": "transporter", "batch": "BATCH-002"},
    {"id": "SENSOR-R-001", "type": "retailer", "batch": "BATCH-001"},
    {"id": "SENSOR-R-002", "type": "retailer", "batch": "BATCH-003"},
]

# Credentials for different roles
TRANSPORTER_CREDS = {"username": "transporter", "password": "demo123"}
RETAILER_CREDS = {"username": "retailer", "password": "demo123"}

# Temperature ranges for different sensor types
TEMP_RANGES = {
    "transporter": (2.0, 8.0),  # Cold chain during transport
    "retailer": (4.0, 10.0),     # Refrigerated storage
}

# Humidity ranges
HUMIDITY_RANGE = (60.0, 85.0)

# Update interval in seconds
UPDATE_INTERVAL = 10


class SensorSimulator:
    def __init__(self):
        self.tokens = {}
        self.running = False
        
    def login(self, username: str, password: str) -> str:
        """Login and get auth token"""
        try:
            response = requests.post(
                f"{BACKEND_URL}/auth/login",
                json={"username": username, "password": password}
            )
            if response.status_code == 200:
                data = response.json()
                token = data.get("token")
                print(f"✓ Logged in as {username}")
                return token
            else:
                print(f"✗ Login failed for {username}: {response.status_code}")
                return None
        except Exception as e:
            print(f"✗ Login error for {username}: {e}")
            return None
    
    def register_sensor(self, token: str, sensor: Dict) -> bool:
        """Register a sensor with the backend"""
        try:
            response = requests.post(
                f"{BACKEND_URL}/sensors/register",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "sensorId": sensor["id"],
                    "batchId": sensor["batch"],
                    "sensorType": sensor["type"]
                }
            )
            if response.status_code == 200:
                print(f"✓ Registered sensor {sensor['id']} for batch {sensor['batch']}")
                return True
            else:
                # Sensor might already be registered
                if response.status_code == 400:
                    print(f"  Sensor {sensor['id']} already registered")
                    return True
                print(f"✗ Failed to register {sensor['id']}: {response.status_code}")
                return False
        except Exception as e:
            print(f"✗ Registration error for {sensor['id']}: {e}")
            return False
    
    def generate_reading(self, sensor_type: str) -> tuple:
        """Generate realistic sensor readings"""
        temp_min, temp_max = TEMP_RANGES.get(sensor_type, (5.0, 10.0))
        hum_min, hum_max = HUMIDITY_RANGE
        
        # Add some random variation
        temperature = round(random.uniform(temp_min, temp_max), 2)
        humidity = round(random.uniform(hum_min, hum_max), 2)
        
        # Occasionally simulate anomalies
        if random.random() < 0.05:  # 5% chance
            temperature += random.choice([-3, 3])  # Temperature spike
        
        return temperature, humidity
    
    def submit_reading(self, token: str, sensor: Dict, temperature: float, humidity: float) -> bool:
        """Submit sensor reading to backend"""
        try:
            response = requests.post(
                f"{BACKEND_URL}/sensors/data",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "batchId": sensor["batch"],
                    "sensorId": sensor["id"],
                    "temperature": temperature,
                    "humidity": humidity
                }
            )
            if response.status_code == 200:
                timestamp = datetime.now().strftime("%H:%M:%S")
                print(f"[{timestamp}] {sensor['id']} → Batch {sensor['batch']}: {temperature}°C, {humidity}%")
                return True
            else:
                print(f"✗ Failed to submit data for {sensor['id']}: {response.status_code}")
                return False
        except Exception as e:
            print(f"✗ Submit error for {sensor['id']}: {e}")
            return False
    
    async def simulate_sensor(self, sensor: Dict):
        """Simulate a single sensor continuously"""
        # Get appropriate token based on sensor type
        if sensor["type"] == "transporter":
            token = self.tokens.get("transporter")
        else:
            token = self.tokens.get("retailer")
        
        if not token:
            print(f"✗ No token available for {sensor['id']}")
            return
        
        # Register sensor once
        self.register_sensor(token, sensor)
        
        # Continuously generate and submit readings
        while self.running:
            temperature, humidity = self.generate_reading(sensor["type"])
            self.submit_reading(token, sensor, temperature, humidity)
            await asyncio.sleep(UPDATE_INTERVAL)
    
    async def run(self):
        """Run all sensor simulations"""
        print("=" * 60)
        print("IoT Sensor Simulator - Real-time Data Generation")
        print("=" * 60)
        
        # Login for each role
        print("\n[1/3] Authenticating...")
        self.tokens["transporter"] = self.login(
            TRANSPORTER_CREDS["username"], 
            TRANSPORTER_CREDS["password"]
        )
        self.tokens["retailer"] = self.login(
            RETAILER_CREDS["username"], 
            RETAILER_CREDS["password"]
        )
        
        if not any(self.tokens.values()):
            print("\n✗ Failed to authenticate. Cannot start simulation.")
            return
        
        print(f"\n[2/3] Configured {len(SENSORS)} sensors")
        for sensor in SENSORS:
            print(f"  • {sensor['id']} ({sensor['type']}) → {sensor['batch']}")
        
        print(f"\n[3/3] Starting simulation (updates every {UPDATE_INTERVAL}s)")
        print("Press Ctrl+C to stop\n")
        
        self.running = True
        
        # Create tasks for all sensors
        tasks = [self.simulate_sensor(sensor) for sensor in SENSORS]
        
        try:
            await asyncio.gather(*tasks)
        except KeyboardInterrupt:
            print("\n\n✓ Simulation stopped by user")
            self.running = False
        except Exception as e:
            print(f"\n✗ Error during simulation: {e}")
            self.running = False


def main():
    """Entry point"""
    simulator = SensorSimulator()
    try:
        asyncio.run(simulator.run())
    except KeyboardInterrupt:
        print("\n✓ Shutting down...")


if __name__ == "__main__":
    main()
