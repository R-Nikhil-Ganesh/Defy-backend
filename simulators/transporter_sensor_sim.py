"""Simple transporter sensor simulator.

Usage:
    python transporter_sensor_sim.py --batch-id BATCH-001 --token transporter
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
    suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"{prefix}-{suffix}".lower()


def _auth_header(token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def register_sensor(base_url: str, sensor_id: str, token: str) -> None:
    payload = {
        "sensorId": sensor_id,
        "sensorType": "transporter",
        "label": "Vehicle Thermal Probe",
        "vehicleOrStoreId": "truck-42",
    }
    response = requests.post(f"{base_url}/sensors/register", json=payload, headers=_auth_header(token), timeout=10)
    response.raise_for_status()
    print("Registered transporter sensor", response.json())


def link_sensor(base_url: str, sensor_id: str, batch_id: str, token: str) -> None:
    payload = {
        "batchId": batch_id,
        "sensorId": sensor_id,
        "locationType": "transporter",
    }
    response = requests.post(f"{base_url}/qr/scan", json=payload, headers=_auth_header(token), timeout=10)
    response.raise_for_status()
    print("Linked sensor to batch", response.json())


def push_reading(base_url: str, sensor_id: str, batch_id: str, token: str) -> None:
    temperature = round(random.uniform(2.5, 10.5), 2)
    humidity = round(random.uniform(70.0, 95.0), 2)
    payload = {
        "sensorId": sensor_id,
        "batchId": batch_id,
        "temperature": temperature,
        "humidity": humidity,
    }
    response = requests.post(f"{base_url}/sensors/data", json=payload, headers=_auth_header(token), timeout=10)
    response.raise_for_status()
    print("Reading", response.json()["latest"])


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulate transporter temperature/humidity telemetry")
    parser.add_argument("--batch-id", required=True, help="Blockchain batch ID to attach to")
    parser.add_argument("--token", required=True, help="Demo API token (use transporter login username)")
    parser.add_argument("--sensor-id", default=None, help="Override generated sensor id")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Backend base URL")
    parser.add_argument("--interval", type=float, default=5.0, help="Seconds between readings")
    args = parser.parse_args()

    sensor_id = args.sensor_id or _random_sensor_id("trans")

    try:
        register_sensor(args.base_url, sensor_id, args.token)
    except requests.HTTPError as exc:
        if exc.response.status_code != 409:
            raise
        print("Sensor already registered; continuing")

    link_sensor(args.base_url, sensor_id, args.batch_id, args.token)

    while True:
        push_reading(args.base_url, sensor_id, args.batch_id, args.token)
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
