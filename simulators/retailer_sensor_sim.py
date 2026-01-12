"""Retailer ambient sensor simulator.

Usage:
    python retailer_sensor_sim.py --batch-id BATCH-001 --token retailer
"""

from __future__ import annotations

import argparse
import random
import string
import time
from typing import Dict

import requests

DEFAULT_BASE_URL = "http://localhost:8000"


def _random_sensor_id(prefix: str) -> str:
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
    return f"{prefix}-{suffix}"


def _auth_header(token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def register_sensor(base_url: str, sensor_id: str, token: str) -> None:
    payload = {
        "sensorId": sensor_id,
        "sensorType": "retailer",
        "label": "Storefront Sensor",
        "vehicleOrStoreId": "store-7",
    }
    response = requests.post(f"{base_url}/sensors/register", json=payload, headers=_auth_header(token), timeout=10)
    response.raise_for_status()
    print("Registered retailer sensor", response.json())


def link_sensor(base_url: str, sensor_id: str, batch_id: str, token: str) -> None:
    payload = {
        "batchId": batch_id,
        "sensorId": sensor_id,
        "locationType": "retailer",
    }
    response = requests.post(f"{base_url}/qr/scan", json=payload, headers=_auth_header(token), timeout=10)
    response.raise_for_status()
    print("Linked retailer sensor", response.json())


def push_reading(base_url: str, sensor_id: str, batch_id: str, token: str) -> None:
    temperature = round(random.uniform(8.0, 18.0), 2)
    humidity = round(random.uniform(45.0, 70.0), 2)
    payload = {
        "sensorId": sensor_id,
        "batchId": batch_id,
        "temperature": temperature,
        "humidity": humidity,
    }
    response = requests.post(f"{base_url}/sensors/data", json=payload, headers=_auth_header(token), timeout=10)
    response.raise_for_status()
    latest = response.json()["latest"]
    print(f"Reading pushed (temp={temperature}C, humidity={humidity}%)-> stage={latest['sensorType']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulate retailer sensors streaming in-store data")
    parser.add_argument("--batch-id", required=True, help="Batch ID to bind the sensor to")
    parser.add_argument("--token", required=True, help="Retailer token (username) for demo auth")
    parser.add_argument("--sensor-id", default=None, help="Optional fixed sensor id")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Backend base URL")
    parser.add_argument("--interval", type=float, default=10.0, help="Seconds between readings")
    args = parser.parse_args()

    sensor_id = args.sensor_id or _random_sensor_id("ret")
    register_sensor(args.base_url, sensor_id, args.token)
    link_sensor(args.base_url, sensor_id, args.batch_id, args.token)

    while True:
        push_reading(args.base_url, sensor_id, args.batch_id, args.token)
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
