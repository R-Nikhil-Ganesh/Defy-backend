"""Marketplace service for parent batches, bids, and Razorpay payments."""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

try:  # pragma: no cover - optional dependency during tests
    import razorpay  # type: ignore
except ImportError:  # pragma: no cover
    razorpay = None


def _utc_now() -> str:
    return datetime.utcnow().replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


class MarketplaceService:
    def __init__(
        self,
        state_path: str,
        advance_percent: float,
        razorpay_key_id: str,
        razorpay_key_secret: str,
    ) -> None:
        self.state_path = Path(state_path)
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.advance_percent = max(0.0, min(1.0, advance_percent))
        self._lock = asyncio.Lock()
        self._state: Dict[str, Any] = {"parents": {}, "requests": {}, "payments": {}}
        self._load_state()
        self.client: Optional[Any] = None
        if razorpay and razorpay_key_id and razorpay_key_secret:
            self.client = razorpay.Client(auth=(razorpay_key_id, razorpay_key_secret))

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------
    def _load_state(self) -> None:
        if self.state_path.exists():
            try:
                self._state = json.loads(self.state_path.read_text(encoding="utf-8"))
            except Exception:
                self._state = {"parents": {}, "requests": {}, "payments": {}}
        else:
            self.state_path.write_text(json.dumps(self._state), encoding="utf-8")

    def _write_state(self) -> None:
        tmp_path = self.state_path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(self._state, indent=2), encoding="utf-8")
        tmp_path.replace(self.state_path)

    # ------------------------------------------------------------------
    # Parent offers
    # ------------------------------------------------------------------
    async def create_parent(self, *, producer: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if payload["basePrice"] <= 0:
            raise ValueError("Base price must be greater than zero")
        if payload["totalQuantity"] <= 0:
            raise ValueError("Total quantity must be greater than zero")

        async with self._lock:
            parent_id = str(uuid.uuid4())
            record = {
                "parentId": parent_id,
                "producer": producer,
                "productType": payload["productType"],
                "unit": payload["unit"],
                "basePrice": payload["basePrice"],
                "totalQuantity": payload["totalQuantity"],
                "availableQuantity": payload["totalQuantity"],
                "createdAt": _utc_now(),
                "metadata": payload.get("metadata") or {},
                "pricingCurrency": payload.get("currency", "INR"),
            }
            self._state["parents"][parent_id] = record
            self._write_state()
            return record.copy()

    async def list_parents(self) -> List[Dict[str, Any]]:
        async with self._lock:
            return [record.copy() for record in self._state["parents"].values()]

    async def get_parent(self, parent_id: str) -> Optional[Dict[str, Any]]:
        async with self._lock:
            record = self._state["parents"].get(parent_id)
            return record.copy() if record else None

    # ------------------------------------------------------------------
    # Retailer requests / bids
    # ------------------------------------------------------------------
    async def create_request(
        self,
        *,
        parent_id: str,
        retailer: str,
        quantity: float,
        bid_price: float,
    ) -> Dict[str, Any]:
        if quantity <= 0:
            raise ValueError("Quantity must be greater than zero")
        if bid_price <= 0:
            raise ValueError("Bid price must be greater than zero")

        async with self._lock:
            parent = self._state["parents"].get(parent_id)
            if not parent:
                raise ValueError("Parent batch not found")
            available = parent["availableQuantity"]
            if quantity > available:
                raise ValueError("Requested quantity exceeds available amount")
            if bid_price < parent["basePrice"]:
                raise ValueError("Bid price cannot be below the producer's base price")

            request_id = str(uuid.uuid4())
            record = {
                "requestId": request_id,
                "parentId": parent_id,
                "retailer": retailer,
                "quantity": quantity,
                "bidPrice": bid_price,
                "status": "pending",
                "createdAt": _utc_now(),
                "currency": parent.get("pricingCurrency", "INR"),
                "advancePercent": self.advance_percent,
                "payment": None,
            }
            parent["availableQuantity"] = max(0.0, available - quantity)
            self._state["requests"][request_id] = record
            self._write_state()
            return record.copy()

    async def get_request(self, request_id: str) -> Optional[Dict[str, Any]]:
        async with self._lock:
            record = self._state["requests"].get(request_id)
            return record.copy() if record else None

    async def list_requests(
        self,
        *,
        parent_id: Optional[str] = None,
        retailer: Optional[str] = None,
        producer: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        async with self._lock:
            results: List[Dict[str, Any]] = []
            for record in self._state["requests"].values():
                if parent_id and record["parentId"] != parent_id:
                    continue
                if retailer and record["retailer"] != retailer:
                    continue
                if producer:
                    parent = self._state["parents"].get(record["parentId"])
                    if not parent or parent.get("producer") != producer:
                        continue
                results.append(record.copy())
            return results

    # ------------------------------------------------------------------
    # Payments
    # ------------------------------------------------------------------
    def _require_client(self):
        if not self.client or razorpay is None:
            raise RuntimeError("Razorpay client is not configured")
        return self.client

    def _calculate_advance_amount(self, quantity: float, price: float) -> int:
        gross = quantity * price * self.advance_percent
        return int(max(1, round(gross * 100)))  # INR in paise

    async def create_payment_order(self, request_id: str) -> Dict[str, Any]:
        async with self._lock:
            request = self._state["requests"].get(request_id)
            if not request:
                raise ValueError("Request not found")
            if request["status"] not in {"pending", "awaiting_payment"}:
                raise ValueError("Request is not awaiting payment")

            parent = self._state["parents"].get(request["parentId"])
            if not parent:
                raise ValueError("Parent batch not found")

            amount = self._calculate_advance_amount(request["quantity"], request["bidPrice"])
            client = self._require_client()
            order = client.order.create(
                {
                    "amount": amount,
                    "currency": request.get("currency", "INR"),
                    "payment_capture": 1,
                    "notes": {
                        "parentId": request["parentId"],
                        "retailer": request["retailer"],
                        "quantity": str(request["quantity"]),
                    },
                }
            )

            payment_record = {
                "orderId": order["id"],
                "requestId": request_id,
                "amount": amount,
                "currency": order["currency"],
                "status": "created",
                "createdAt": _utc_now(),
            }
            self._state["payments"][order["id"]] = payment_record
            request["status"] = "awaiting_payment"
            request["payment"] = payment_record
            self._write_state()
            return {
                "order": order,
                "advanceAmount": amount,
                "currency": order["currency"],
            }

    async def confirm_payment(
        self,
        *,
        request_id: str,
        payment_id: str,
        order_id: str,
    ) -> Dict[str, Any]:
        async with self._lock:
            request = self._state["requests"].get(request_id)
            if not request:
                raise ValueError("Request not found")
            payment = self._state["payments"].get(order_id)
            if not payment:
                raise ValueError("Payment order not found")
            if payment.get("requestId") != request_id:
                raise ValueError("Payment order does not belong to this request")

            payment["status"] = "paid"
            payment["paymentId"] = payment_id
            payment["paidAt"] = _utc_now()
            request["status"] = "paid"
            request["payment"] = payment
            self._write_state()
            return {
                "request": request.copy(),
                "payment": payment.copy(),
            }

    async def mark_fulfilled(self, request_id: str, batch_id: str) -> None:
        async with self._lock:
            request = self._state["requests"].get(request_id)
            if not request:
                raise ValueError("Request not found")
            if request.get("status") != "paid":
                raise ValueError("Request must be paid before fulfillment")

            request["status"] = "fulfilled"
            request["childBatchId"] = batch_id
            request["fulfilledAt"] = _utc_now()
            self._write_state()
