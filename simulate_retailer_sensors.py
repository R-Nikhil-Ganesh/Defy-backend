"""
Retailer IoT Sensor Simulator
Simulates retail storage sensors monitoring produce in stores
"""

import asyncio
import random
from datetime import datetime
import requests
from typing import List, Dict

# Configuration
BACKEND_URL = "http://localhost:8000"

# Retailer sensors - monitoring refrigerated storage at different stores
SENSORS = [
    {"id": "SENSOR-R-001", "type": "retailer", "batch": "BATCH-001", "store": "Store A"},
    {"id": "SENSOR-R-002", "type": "retailer", "batch": "BATCH-002", "store": "Store B"},
]

# Retailer credentials
RETAILER_CREDS = {"username": "retailer", "password": "demo123"}

# Retail storage temperature range (slightly higher than transport)
TEMP_RANGE = (4.0, 10.0)  # °C - Refrigerated display storage
HUMIDITY_RANGE = (65.0, 80.0)  # % - Retail environment

# Update interval in seconds
UPDATE_INTERVAL = 15  # Every 15 seconds


class RetailerSensorSimulator:
    def __init__(self):
        self.token = None
        self.running = False
        
    def login(self) -> bool:
        """Login as retailer"""
        try:
            response = requests.post(
                f"{BACKEND_URL}/auth/login",
                json=RETAILER_CREDS
            )
            if response.status_code == 200:
                data = response.json()
                self.token = data.get("token")
                print(f"✓ Logged in as retailer")
                return True
            else:
                print(f"✗ Login failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"✗ Login error: {e}")
            return False
    
    def register_sensor(self, sensor: Dict) -> bool:
        """Register a sensor"""
        try:
            response = requests.post(
                f"{BACKEND_URL}/sensors/register",
                headers={"Authorization": f"Bearer {self.token}"},
                json={
                    "sensorId": sensor["id"],
                    "batchId": sensor["batch"],
                    "sensorType": sensor["type"]
                }
            )
            if response.status_code == 200:
                print(f"✓ {sensor['store']}: Registered {sensor['id']} → Batch {sensor['batch']}")
                return True
            elif response.status_code == 400:
                print(f"  {sensor['store']}: {sensor['id']} already registered")
                return True
            else:
                print(f"✗ Failed to register {sensor['id']}: {response.status_code}")
                return False
        except Exception as e:
            print(f"✗ Registration error: {e}")
            return False
    
    def generate_reading(self) -> tuple:
        """Generate realistic retail storage readings"""
        temperature = round(random.uniform(*TEMP_RANGE), 2)
        humidity = round(random.uniform(*HUMIDITY_RANGE), 2)
        
        # Simulate door opening spikes (10% chance)
        if random.random() < 0.10:
            temperature += random.uniform(1, 2)  # Temperature increases when doors open
            humidity -= random.uniform(2, 5)  # Humidity drops
        
        # Simulate cooling cycle variations
        temperature += random.uniform(-0.5, 0.5)
        
        return round(temperature, 2), round(humidity, 2)
    
    def submit_reading(self, sensor: Dict, temperature: float, humidity: float) -> bool:
        """Submit sensor reading"""
        try:
            response = requests.post(
                f"{BACKEND_URL}/sensors/data",
                headers={"Authorization": f"Bearer {self.token}"},
                json={
                    "batchId": sensor["batch"],
                    "sensorId": sensor["id"],
                    "temperature": temperature,
                    "humidity": humidity
                }
            )
            if response.status_code == 200:
                timestamp = datetime.now().strftime("%H:%M:%S")
                
                # Color-code temperature warnings
                temp_status = "✓" if temperature < 8.0 else "⚠" if temperature < 10.0 else "✗"
                
                print(f"[{timestamp}] {sensor['store']:9} | {sensor['id']} | "
                      f"{temp_status} {temperature:5.2f}°C | {humidity:5.2f}% | Batch {sensor['batch']}")
                return True
            else:
                print(f"✗ Failed to submit for {sensor['id']}: {response.status_code}")
                return False
        except Exception as e:
            print(f"✗ Submit error: {e}")
            return False
    
    async def simulate_sensor(self, sensor: Dict):
        """Simulate a single retail sensor"""
        # Register once
        self.register_sensor(sensor)
        
        # Continuous monitoring
        while self.running:
            temperature, humidity = self.generate_reading()
            self.submit_reading(sensor, temperature, humidity)
            await asyncio.sleep(UPDATE_INTERVAL)
    
    async def run(self):
        """Run retailer sensor simulation"""
        print("=" * 80)
        print("RETAILER IoT Sensor Simulator - Refrigerated Storage Monitoring")
        print("=" * 80)
        
        # Login
        print("\n[1/3] Authenticating as retailer...")
        if not self.login():
            print("\n✗ Authentication failed. Cannot start simulation.")
            return
        
        print(f"\n[2/3] Monitoring {len(SENSORS)} retail storage sensors:")
        for sensor in SENSORS:
            print(f"  • {sensor['store']}: {sensor['id']} monitoring Batch {sensor['batch']}")
        
        print(f"\n[3/3] Starting real-time monitoring (updates every {UPDATE_INTERVAL}s)")
        print("Legend: ✓ Good (<8°C) | ⚠ Acceptable (8-10°C) | ✗ Warning (>10°C)")
        print("\nPress Ctrl+C to stop\n")
        print("-" * 80)
        
        self.running = True
        
        # Create tasks for all sensors
        tasks = [self.simulate_sensor(sensor) for sensor in SENSORS]
        
        try:
            await asyncio.gather(*tasks)
        except KeyboardInterrupt:
            print("\n" + "-" * 80)
            print("\n✓ Monitoring stopped by user")
            self.running = False
        except Exception as e:
            print(f"\n✗ Error during monitoring: {e}")
            self.running = False


def main():
    """Entry point"""
    simulator = RetailerSensorSimulator()
    try:
        asyncio.run(simulator.run())
    except KeyboardInterrupt:
        print("\n✓ Shutting down...")


if __name__ == "__main__":
    main()
