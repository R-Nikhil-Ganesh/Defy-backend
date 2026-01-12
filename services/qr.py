"""QR code utilities for binding sensors to blockchain batches."""

from __future__ import annotations

import base64
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

import qrcode


class QRService:
    def __init__(self, cache_dir: str):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _build_payload(self, batch_id: str, stage: str, metadata: Optional[Dict]) -> Dict:
        return {
            "batchId": batch_id,
            "stage": stage,
            "metadata": metadata or {},
            "issuedAt": datetime.utcnow().replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z"),
        }

    def generate(self, batch_id: str, stage: str, metadata: Optional[Dict] = None) -> Dict[str, str]:
        payload = self._build_payload(batch_id, stage, metadata)
        payload_json = json.dumps(payload)

        qr_img = qrcode.make(payload_json)
        buffer = io.BytesIO()
        qr_img.save(buffer, format="PNG")
        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")

        cache_path = self.cache_dir / f"{batch_id}_{stage}.json"
        cache_path.write_text(payload_json, encoding="utf-8")

        return {
            "batchId": batch_id,
            "payload": payload_json,
            "qrImageBase64": encoded,
        }

    @staticmethod
    def decode_payload(payload: str) -> Dict:
        try:
            return json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ValueError("Invalid QR payload") from exc
