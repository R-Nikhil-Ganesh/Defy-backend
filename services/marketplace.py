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
        self._state: Dict[str, Any] = {
            "parents": {},
            "requests": {},
            "payments": {},
            "meta": {"parentSequence": 0},
        }
        self._load_state()
        self._ensure_state_defaults()
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
                self._state = {
                    "parents": {},
                    "requests": {},
                    "payments": {},
                    "meta": {"parentSequence": 0},
                }
        else:
            self.state_path.write_text(json.dumps(self._state), encoding="utf-8")

    def _write_state(self) -> None:
        tmp_path = self.state_path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(self._state, indent=2), encoding="utf-8")
        tmp_path.replace(self.state_path)

    def _ensure_state_defaults(self) -> None:
        self._state.setdefault("parents", {})
        self._state.setdefault("requests", {})
        self._state.setdefault("payments", {})
        meta = self._state.setdefault("meta", {})
        sequence = meta.get("parentSequence")
        if not isinstance(sequence, int) or sequence < 0:
            sequence = 0

        for parent in self._state["parents"].values():
            if "parentBatchNumber" not in parent:
                parent["parentBatchNumber"] = parent.get("parentId") or str(uuid.uuid4())
            identifier = parent.get("parentBatchNumber", "")
            if identifier.startswith("PB-"):
                suffix = identifier.split("-")[-1]
                if suffix.isdigit():
                    sequence = max(sequence, int(suffix))
            parent.setdefault("status", "published")
            parent.setdefault("publishedAt", parent.get("createdAt"))

        meta["parentSequence"] = sequence

    def _next_parent_sequence(self) -> int:
        meta = self._state.setdefault("meta", {})
        meta["parentSequence"] = int(meta.get("parentSequence", 0)) + 1
        return meta["parentSequence"]

    def _generate_parent_batch_number(self) -> str:
        sequence = self._next_parent_sequence()
        return f"PB-{sequence:05d}"

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
            batch_number = self._generate_parent_batch_number()
            record = {
                "parentId": parent_id,
                "parentBatchNumber": batch_number,
                "producer": producer,
                "productType": payload["productType"],
                "unit": payload["unit"],
                "basePrice": payload["basePrice"],
                "totalQuantity": payload["totalQuantity"],
                "availableQuantity": payload["totalQuantity"],
                "createdAt": _utc_now(),
                "metadata": payload.get("metadata") or {},
                "pricingCurrency": payload.get("currency", "INR"),
                "status": "draft",
                "publishedAt": None,
            }
            self._state["parents"][parent_id] = record
            self._write_state()
            return record.copy()

    async def list_parents(
        self,
        *,
        status: Optional[str] = None,
        producer: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        async with self._lock:
            results: List[Dict[str, Any]] = []
            for record in self._state["parents"].values():
                if status and record.get("status") != status:
                    continue
                if producer and record.get("producer") != producer:
                    continue
                results.append(record.copy())
            return sorted(results, key=lambda item: item["createdAt"], reverse=True)

    async def get_parent(self, parent_id: str) -> Optional[Dict[str, Any]]:
        async with self._lock:
            record = self._state["parents"].get(parent_id)
            return record.copy() if record else None

    async def publish_parent(self, parent_id: str, *, producer: str) -> Dict[str, Any]:
        async with self._lock:
            parent = self._state["parents"].get(parent_id)
            if not parent:
                raise ValueError("Parent batch not found")
            if parent.get("producer") != producer:
                raise ValueError("Cannot publish batches you do not own")
            if parent.get("status") == "published":
                raise ValueError("Parent batch already published")

            parent["status"] = "published"
            parent["publishedAt"] = _utc_now()
            self._write_state()
            return parent.copy()

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
            if parent.get("status") != "published":
                raise ValueError("Parent batch must be published before bidding")

            available = parent["availableQuantity"]
            if quantity > available:
                raise ValueError("Requested quantity exceeds available amount")
            if bid_price < parent["basePrice"]:
                raise ValueError("Bid price cannot be below the producer's base price")

            request_id = str(uuid.uuid4())
            record = {
                "requestId": request_id,
                "parentId": parent_id,
                "parentBatchNumber": parent.get("parentBatchNumber"),
                "parentProductType": parent.get("productType"),
                "producer": parent.get("producer"),
                "retailer": retailer,
                "quantity": quantity,
                "bidPrice": bid_price,
                "status": "pending_approval",
                "createdAt": _utc_now(),
                "approvedAt": None,
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

    async def approve_request(self, request_id: str, *, producer: str) -> Dict[str, Any]:
        async with self._lock:
            request = self._state["requests"].get(request_id)
            if not request:
                raise ValueError("Request not found")
            if request.get("producer") != producer:
                raise ValueError("Only the producer can approve this bid")
            if request.get("status") != "pending_approval":
                raise ValueError("Request is not pending approval")

            request["status"] = "approved"
            request["approvedAt"] = _utc_now()
            self._write_state()
            return request.copy()

    async def reject_request(self, request_id: str, *, producer: str) -> Dict[str, Any]:
        async with self._lock:
            request = self._state["requests"].get(request_id)
            if not request:
                raise ValueError("Request not found")
            if request.get("producer") != producer:
                raise ValueError("Only the producer can reject this bid")
            if request.get("status") != "pending_approval":
                raise ValueError("Request is not pending approval")

            parent = self._state["parents"].get(request["parentId"])
            if parent:
                parent["availableQuantity"] = parent["availableQuantity"] + request["quantity"]

            request["status"] = "rejected"
            request["rejectedAt"] = _utc_now()
            self._write_state()
            return request.copy()

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
                    owner = record.get("producer")
                    if owner != producer:
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
            if request["status"] not in {"approved", "awaiting_payment"}:
                raise ValueError("Request must be approved before payment")

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
