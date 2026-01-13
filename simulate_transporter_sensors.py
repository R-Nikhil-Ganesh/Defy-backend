"""
Transporter IoT Sensor Simulator
Simulates transport vehicle sensors monitoring cold chain during delivery
Supports two modes: NORMAL (in-range) and VIOLATION (out-of-range)
"""

import asyncio
import random
import sys
from datetime import datetime
import requests
from typing import List, Dict

# Configuration
BACKEND_URL = "http://localhost:8000"

# Transporter sensors - monitoring vehicles during transport
# Batch ID will be auto-detected from sensor linkage (no manual entry needed)
SENSORS = [
    {"id": "SENSOR-T-008", "type": "transporter", "vehicle": "Truck-B", "route": "Warehouse→Store"},
]

# Transporter credentials
TRANSPORTER_CREDS = {"username": "transporter", "password": "demo123"}

# Product-specific optimal ranges (will be detected from linked batch)
PRODUCT_RANGES = {
    "apple": {"temp": (-1.0, 4.0), "humidity": (90.0, 95.0)},
    "banana": {"temp": (13.0, 15.0), "humidity": (85.0, 95.0)},
    "mango": {"temp": (10.0, 13.0), "humidity": (85.0, 90.0)},
    "tomato": {"temp": (10.0, 13.0), "humidity": (85.0, 95.0)},
    "potato": {"temp": (3.0, 10.0), "humidity": (85.0, 95.0)},
    "default": {"temp": (2.0, 6.0), "humidity": (70.0, 85.0)},  # Fallback
}

# Update interval in seconds
UPDATE_INTERVAL = 10  # Every 10 seconds (more frequent for transit monitoring)


class TransporterSensorSimulator:
    def __init__(self, mode: str = "normal"):
        self.token = None
        self.running = False
        self.trip_progress = {sensor["id"]: 0 for sensor in SENSORS}
        self.mode = mode.lower()  # 'normal' or 'violation'
        self.batch_products = {}  # Cache for batch product types
        
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
                    "sensorType": sensor["type"],
                    "label": f"{sensor['vehicle']} - {sensor['route']}",
                    "vehicleOrStoreId": sensor["vehicle"]
                }
            )
            if response.status_code == 200:
                print(f"✓ {sensor['vehicle']:9} | Registered {sensor['id']} | {sensor['route']}")
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
    
    def get_batch_product_type(self, batch_id: str) -> str:
        """Get the product type for a batch"""
        if batch_id in self.batch_products:
            return self.batch_products[batch_id]
        
        try:
            response = requests.get(
                f"{BACKEND_URL}/batch/{batch_id}",
                headers={"Authorization": f"Bearer {self.token}"}
            )
            if response.status_code == 200:
                data = response.json()
                product_type = data.get("productType", "default").lower()
                self.batch_products[batch_id] = product_type
                return product_type
        except Exception:
            pass
        return "default"
    
    def generate_reading_normal(self, product_type: str) -> tuple:
        """Generate readings WITHIN acceptable range for the product"""
        ranges = PRODUCT_RANGES.get(product_type, PRODUCT_RANGES["default"])
        
        # Generate values well within the range (centered)
        temp_min, temp_max = ranges["temp"]
        hum_min, hum_max = ranges["humidity"]
        
        # Stay in the middle 70% of the range for safety margin
        temp_range_size = temp_max - temp_min
        hum_range_size = hum_max - hum_min
        
        temperature = temp_min + (temp_range_size * 0.15) + random.uniform(0, temp_range_size * 0.7)
        humidity = hum_min + (hum_range_size * 0.15) + random.uniform(0, hum_range_size * 0.7)
        
        # Add small natural variations
        temperature += random.uniform(-0.2, 0.2)
        humidity += random.uniform(-1, 1)
        
        return round(temperature, 2), round(humidity, 2)
    
    def generate_reading_violation(self, product_type: str) -> tuple:
        """Generate readings OUTSIDE acceptable range to trigger violations"""
        ranges = PRODUCT_RANGES.get(product_type, PRODUCT_RANGES["default"])
        
        temp_min, temp_max = ranges["temp"]
        hum_min, hum_max = ranges["humidity"]
        
        # Randomly choose to violate temperature, humidity, or both
        violation_type = random.choice(["temp_low", "temp_high", "humidity_low", "humidity_high", "both_low", "both_high"])
        
        if violation_type == "temp_low":
            temperature = temp_min - random.uniform(2, 8)  # Below minimum
            humidity = (hum_min + hum_max) / 2  # Keep humidity normal
        elif violation_type == "temp_high":
            temperature = temp_max + random.uniform(2, 8)  # Above maximum
            humidity = (hum_min + hum_max) / 2
        elif violation_type == "humidity_low":
            temperature = (temp_min + temp_max) / 2  # Keep temp normal
            humidity = hum_min - random.uniform(5, 15)  # Below minimum
        elif violation_type == "humidity_high":
            temperature = (temp_min + temp_max) / 2
            humidity = min(100, hum_max + random.uniform(2, 8))  # Above maximum (cap at 100%)
        elif violation_type == "both_low":
            temperature = temp_min - random.uniform(2, 6)
            humidity = hum_min - random.uniform(5, 15)
        else:  # both_high
            temperature = temp_max + random.uniform(2, 6)
            humidity = min(100, hum_max + random.uniform(2, 8))
        
        return round(temperature, 2), round(max(0, min(100, humidity)), 2)
    
    def generate_reading(self, sensor_id: str, batch_id: str) -> tuple:
        """Generate readings based on mode (normal or violation)"""
        product_type = self.get_batch_product_type(batch_id)
        
        if self.mode == "violation":
            return self.generate_reading_violation(product_type)
        else:
            return self.generate_reading_normal(product_type)
    
    def get_linked_batch(self, sensor_id: str) -> str:
        """Get the batch ID that this sensor is currently linked to"""
        try:
            response = requests.get(
                f"{BACKEND_URL}/sensors/{sensor_id}/binding",
                headers={"Authorization": f"Bearer {self.token}"}
            )
            if response.status_code == 200:
                data = response.json()
                return data.get("batchId", "Not Linked")
            return "Not Linked"
        except Exception:
            return "Not Linked"
    
    def submit_reading(self, sensor: Dict, temperature: float, humidity: float) -> bool:
        """Submit sensor reading (batch auto-detected from sensor linkage)"""
        # Get current batch linkage
        batch_id = sensor.get("current_batch") or self.get_linked_batch(sensor["id"])
        
        if batch_id == "Not Linked":
            print(f"⚠ {sensor['vehicle']:9} | {sensor['id']} not linked to any batch. Link it via QR scan first.")
            return False
        
        # Update sensor's current batch
        sensor["current_batch"] = batch_id
        
        try:
            response = requests.post(
                f"{BACKEND_URL}/sensors/data",
                headers={"Authorization": f"Bearer {self.token}"},
                json={
                    "sensorId": sensor["id"],
                    "temperature": temperature,
                    "humidity": humidity
                }
            )
            if response.status_code == 200:
                timestamp = datetime.now().strftime("%H:%M:%S")
                
                # Status indicator based on mode
                if self.mode == "violation":
                    status_icon = "🚨"
                    status_text = "VIOLATING"
                else:
                    status_icon = "✓"
                    status_text = "NORMAL"
                
                # Trip progress
                progress = self.trip_progress.get(sensor["id"], 0)
                progress_bar = "█" * (progress // 10) + "░" * (10 - progress // 10)
                
                print(f"[{timestamp}] {sensor['vehicle']:9} | {sensor['id']} | "
                      f"{status_icon} {temperature:5.2f}°C | {humidity:5.2f}% | "
                      f"[{progress_bar}] {progress}% | Batch {batch_id} | {status_text}")
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
        
        # Get linked batch
        batch_id = self.get_linked_batch(sensor["id"])
        if batch_id == "Not Linked":
            print(f"⚠ {sensor['vehicle']} sensor not linked. Skipping.")
            return
        
        sensor["current_batch"] = batch_id
        product_type = self.get_batch_product_type(batch_id)
        
        print(f"  ✓ {sensor['vehicle']} monitoring Batch {batch_id} ({product_type.upper()}) in {self.mode.upper()} mode")
        
        # Continuous monitoring during transport
        while self.running:
            temperature, humidity = self.generate_reading(sensor["id"], batch_id)
            self.submit_reading(sensor, temperature, humidity)
            
            # Update trip progress
            self.trip_progress[sensor["id"]] = (self.trip_progress.get(sensor["id"], 0) + 1) % 100
            
            await asyncio.sleep(UPDATE_INTERVAL)
    
    async def run(self):
        """Run transporter sensor simulation"""
        print("=" * 90)
        print("TRANSPORTER IoT Sensor Simulator - Cold Chain Transit Monitoring")
        print("=" * 90)
        
        mode_display = "🚨 VIOLATION MODE" if self.mode == "violation" else "✓ NORMAL MODE"
        print(f"\n📡 Running in: {mode_display}")
        
        if self.mode == "violation":
            print("   ⚠️  Sensors will generate OUT-OF-RANGE readings to trigger blockchain alerts")
        else:
            print("   ✅ Sensors will generate WITHIN-RANGE readings (normal operation)")
        
        # Login
        print("\n[1/3] Authenticating as transporter...")
        if not self.login():
            print("\n✗ Authentication failed. Cannot start simulation.")
            return
        
        print(f"\n[2/3] Monitoring {len(SENSORS)} transport vehicle sensors:")
        for sensor in SENSORS:
            print(f"  • {sensor['vehicle']}: {sensor['id']} ({sensor['route']})")
            print(f"    → Link to batch via QR scan in Consumer Audit page")
        
        print(f"\n[3/3] Starting monitoring (updates every {UPDATE_INTERVAL}s)")
        print("Press Ctrl+C to stop\n")
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
    # Parse command line arguments
    mode = "normal"
    if len(sys.argv) > 1:
        if sys.argv[1].lower() in ["violation", "v", "--violation", "-v"]:
            mode = "violation"
        elif sys.argv[1].lower() in ["normal", "n", "--normal", "-n"]:
            mode = "normal"
        elif sys.argv[1].lower() in ["help", "--help", "-h"]:
            print("\nTransporter Sensor Simulator")
            print("=" * 60)
            print("\nUsage:")
            print("  python simulate_transporter_sensors.py [mode]")
            print("\nModes:")
            print("  normal     - Generate readings within acceptable range (default)")
            print("  violation  - Generate readings outside range to trigger alerts")
            print("\nExamples:")
            print("  python simulate_transporter_sensors.py normal")
            print("  python simulate_transporter_sensors.py violation")
            print("\n" + "=" * 60)
            return
    
    simulator = TransporterSensorSimulator(mode=mode)
    try:
        asyncio.run(simulator.run())
    except KeyboardInterrupt:
        print("\n✓ Shutting down...")


if __name__ == "__main__":
    main()
