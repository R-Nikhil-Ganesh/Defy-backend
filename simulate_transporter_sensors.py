"""
Transporter IoT Sensor Simulator
Simulates transport vehicle sensors monitoring cold chain during delivery
"""

import asyncio
import random
from datetime import datetime
import requests
from typing import List, Dict

# Configuration
BACKEND_URL = "http://localhost:8000"

# Transporter sensors - monitoring vehicles during transport
# Using common batch IDs that likely exist from previous demos
SENSORS = [
    {"id": "SENSOR-T-006", "type": "transporter", "batch": "M-1", "vehicle": "Truck-A", "route": "Farm→Warehouse"},
    {"id": "SENSOR-T-005", "type": "transporter", "batch": "BATCH-002", "vehicle": "Truck-B", "route": "Warehouse→Store"},
]

# Transporter credentials
TRANSPORTER_CREDS = {"username": "transporter", "password": "demo123"}

# Cold chain transport temperature range (stricter than storage)
TEMP_RANGE = (2.0, 6.0)  # °C - Cold chain during transport
HUMIDITY_RANGE = (70.0, 85.0)  # % - Transport conditions

# Update interval in seconds
UPDATE_INTERVAL = 10  # Every 10 seconds (more frequent for transit monitoring)


class TransporterSensorSimulator:
    def __init__(self):
        self.token = None
        self.running = False
        self.trip_progress = {sensor["id"]: 0 for sensor in SENSORS}
        
    def login(self) -> bool:
        """Login as transporter"""
        try:
            response = requests.post(
                f"{BACKEND_URL}/auth/login",
                json=TRANSPORTER_CREDS
            )
            if response.status_code == 200:
                data = response.json()
                self.token = data.get("token")
                print(f"✓ Logged in as transporter")
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
                print(f"✓ {sensor['vehicle']:9} | Registered {sensor['id']} → Batch {sensor['batch']} | {sensor['route']}")
                return True
            elif response.status_code == 400:
                print(f"  {sensor['vehicle']:9} | {sensor['id']} already registered")
                return True
            else:
                print(f"✗ Failed to register {sensor['id']}: {response.status_code}")
                return False
        except Exception as e:
            print(f"✗ Registration error: {e}")
            return False
    
    def generate_reading(self, sensor_id: str) -> tuple:
        """Generate realistic transport readings with trip simulation"""
        # Simulate trip progression
        self.trip_progress[sensor_id] = (self.trip_progress[sensor_id] + 1) % 100
        progress = self.trip_progress[sensor_id]
        
        # Base temperature and humidity
        temperature = random.uniform(*TEMP_RANGE)
        humidity = random.uniform(*HUMIDITY_RANGE)
        
        # Simulate loading/unloading events (door opening)
        if progress < 5 or progress > 95:  # Start/end of trip
            temperature += random.uniform(2, 4)  # Significant spike when doors open
            humidity -= random.uniform(5, 10)
        
        # Simulate road vibrations affecting readings slightly
        temperature += random.uniform(-0.3, 0.3)
        humidity += random.uniform(-2, 2)
        
        # Simulate refrigeration unit cycling
        if progress % 20 < 3:
            temperature -= random.uniform(0.5, 1.0)  # Cooling cycle
        
        # Occasional road condition impacts (10% chance)
        if random.random() < 0.10:
            temperature += random.uniform(0.5, 1.5)  # Hot weather, traffic delays
        
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
                
                # Cold chain compliance indicators
                if temperature <= 4.0:
                    temp_status = "✓✓"  # Excellent
                elif temperature <= 6.0:
                    temp_status = "✓ "  # Good
                elif temperature <= 8.0:
                    temp_status = "⚠ "  # Warning
                else:
                    temp_status = "✗✗"  # Critical
                
                # Trip progress
                progress = self.trip_progress[sensor["id"]]
                progress_bar = "█" * (progress // 10) + "░" * (10 - progress // 10)
                
                print(f"[{timestamp}] {sensor['vehicle']:9} | {sensor['id']} | "
                      f"{temp_status} {temperature:5.2f}°C | {humidity:5.2f}% | "
                      f"[{progress_bar}] {progress}% | Batch {sensor['batch']}")
                return True
            else:
                print(f"✗ Failed to submit for {sensor['id']}: {response.status_code}")
                return False
        except Exception as e:
            print(f"✗ Submit error: {e}")
            return False
    
    async def simulate_sensor(self, sensor: Dict):
        """Simulate a single transport sensor"""
        # Register once
        self.register_sensor(sensor)
        
        # Continuous monitoring during transport
        while self.running:
            temperature, humidity = self.generate_reading(sensor["id"])
            self.submit_reading(sensor, temperature, humidity)
            await asyncio.sleep(UPDATE_INTERVAL)
    
    async def run(self):
        """Run transporter sensor simulation"""
        print("=" * 90)
        print("TRANSPORTER IoT Sensor Simulator - Cold Chain Transit Monitoring")
        print("=" * 90)
        
        # Login
        print("\n[1/3] Authenticating as transporter...")
        if not self.login():
            print("\n✗ Authentication failed. Cannot start simulation.")
            return
        
        print(f"\n[2/3] Monitoring {len(SENSORS)} transport vehicle sensors:")
        for sensor in SENSORS:
            print(f"  • {sensor['vehicle']}: {sensor['id']} carrying Batch {sensor['batch']} ({sensor['route']})")
        
        print(f"\n[3/3] Starting cold chain monitoring (updates every {UPDATE_INTERVAL}s)")
        print("Legend: ✓✓ Excellent (≤4°C) | ✓ Good (4-6°C) | ⚠ Warning (6-8°C) | ✗✗ Critical (>8°C)")
        print("\nPress Ctrl+C to stop\n")
        print("-" * 90)
        
        self.running = True
        
        # Create tasks for all sensors
        tasks = [self.simulate_sensor(sensor) for sensor in SENSORS]
        
        try:
            await asyncio.gather(*tasks)
        except KeyboardInterrupt:
            print("\n" + "-" * 90)
            print("\n✓ Monitoring stopped by user")
            self.running = False
        except Exception as e:
            print(f"\n✗ Error during monitoring: {e}")
            self.running = False


def main():
    """Entry point"""
    simulator = TransporterSensorSimulator()
    try:
        asyncio.run(simulator.run())
    except KeyboardInterrupt:
        print("\n✓ Shutting down...")


if __name__ == "__main__":
    main()
