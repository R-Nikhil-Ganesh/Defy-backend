from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import logging
import uvicorn

from blockchain import BlockchainService
from schemas import (
    CreateBatchRequest,
    UpdateStageRequest,
    ReportAlertRequest,
    BatchResponse,
    SuccessResponse,
    LoginRequest,
    LoginResponse,
    UserInfo,
    BatchStage,
    SensorRegistrationRequest,
    SensorRegistrationResponse,
    SensorReadingRequest,
    SensorReadingResponse,
    SensorReading,
    SensorInfo,
    SensorListResponse,
    QRCodeRequest,
    QRCodeResponse,
    QRScanRequest,
    QRScanResponse,
    FreshnessScanResponse,
    ShelfLifePredictionRequest,
    ShelfLifePredictionResponse,
    SensorType,
    ParentOfferRequest,
    ParentOfferResponse,
    RetailerBidRequest,
    MarketplaceRequestResponse,
    MarketplacePaymentInfo,
    PaymentOrderResponse,
    PaymentConfirmationRequest,
    FulfillBidRequest,
)
from config import settings
from auth import (
    auth_service, 
    get_current_user, 
    require_admin, 
    require_retailer_or_transporter,
    require_admin_or_retailer,
    require_admin_or_producer,
    require_supply_chain_roles,
    require_producer,
    require_retailer,
    require_transporter,
    require_producer_or_retailer,
    User,
    UserRole
)
from services import (
    SensorRegistry,
    QRService,
    FreshnessClassifier,
    ShelfLifePredictor,
    FreshnessPrediction,
    ShelfLifeResult,
    MarketplaceService,
)


logger = logging.getLogger("freshchain.backend")

# Global services
blockchain_service: Optional[BlockchainService] = None
sensor_registry: Optional[SensorRegistry] = None
qr_service: Optional[QRService] = None
freshness_classifier: Optional[FreshnessClassifier] = None
shelf_life_predictor: Optional[ShelfLifePredictor] = None
marketplace_service: Optional[MarketplaceService] = None


def _require_service(service, name: str):
    if service is None:
        raise HTTPException(status_code=503, detail=f"{name} service is not available")
    return service


def _parse_iso(timestamp_str: str) -> datetime:
    return datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))


def _datetime_to_iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _map_reading(record: Dict[str, Any]) -> SensorReading:
    temp = record["temperature"]
    
    # Determine temperature status
    if temp < settings.TEMP_MIN_THRESHOLD:
        temp_status = "Too Low"
    elif temp > settings.TEMP_MAX_THRESHOLD:
        temp_status = "Too High"
    else:
        temp_status = "Normal"
    
    return SensorReading(
        batchId=record["batchId"],
        sensorId=record["sensorId"],
        sensorType=SensorType(record["sensorType"]),
        temperature=temp,
        humidity=record["humidity"],
        capturedAt=_parse_iso(record["capturedAt"]),
        source=record.get("source", "sensor"),
        temperatureStatus=temp_status,
    )


def _map_parent_offer(record: Dict[str, Any]) -> ParentOfferResponse:
    published_at = record.get("publishedAt")
    return ParentOfferResponse(
        parentId=record["parentId"],
        parentBatchNumber=record.get("parentBatchNumber", record["parentId"]),
        producer=record["producer"],
        productType=record["productType"],
        unit=record["unit"],
        basePrice=record["basePrice"],
        totalQuantity=record["totalQuantity"],
        availableQuantity=record["availableQuantity"],
        pricingCurrency=record.get("pricingCurrency", "INR"),
        createdAt=_parse_iso(record["createdAt"]),
        status=record.get("status", "published"),
        publishedAt=_parse_iso(published_at) if published_at else None,
        metadata=record.get("metadata"),
    )


def _map_payment_info(payment: Dict[str, Any]) -> MarketplacePaymentInfo:
    paid_at = payment.get("paidAt")
    return MarketplacePaymentInfo(
        orderId=payment["orderId"],
        amount=payment["amount"],
        currency=payment.get("currency", "INR"),
        status=payment.get("status", "created"),
        createdAt=_parse_iso(payment["createdAt"]),
        paymentId=payment.get("paymentId"),
        paidAt=_parse_iso(paid_at) if paid_at else None,
    )


def _map_marketplace_request(record: Dict[str, Any]) -> MarketplaceRequestResponse:
    payment = record.get("payment")
    fulfilled_at = record.get("fulfilledAt")
    approved_at = record.get("approvedAt")
    return MarketplaceRequestResponse(
        requestId=record["requestId"],
        parentId=record["parentId"],
        parentBatchNumber=record.get("parentBatchNumber"),
        parentProductType=record.get("parentProductType"),
        retailer=record["retailer"],
        producer=record.get("producer"),
        quantity=record["quantity"],
        bidPrice=record["bidPrice"],
        status=record["status"],
        createdAt=_parse_iso(record["createdAt"]),
        approvedAt=_parse_iso(approved_at) if approved_at else None,
        currency=record.get("currency", "INR"),
        advancePercent=record.get("advancePercent", settings.MARKETPLACE_ADVANCE_PERCENT),
        payment=_map_payment_info(payment) if payment else None,
        childBatchId=record.get("childBatchId"),
        fulfilledAt=_parse_iso(fulfilled_at) if fulfilled_at else None,
    )


async def _resolve_environmental_context(
    batch_id: str,
    temperature_override: Optional[float],
    humidity_override: Optional[float],
    sample_limit: int = 50,
):
    registry = _require_service(sensor_registry, "Sensor registry")
    raw_history = await registry.get_batch_readings(batch_id, limit=sample_limit)
    temps = [entry["temperature"] for entry in raw_history]
    hums = [entry["humidity"] for entry in raw_history]

    resolved_temp = temperature_override if temperature_override is not None else (sum(temps) / len(temps) if temps else None)
    resolved_humidity = humidity_override if humidity_override is not None else (sum(hums) / len(hums) if hums else None)

    simple_history = [{"temperature": r["temperature"], "humidity": r["humidity"]} for r in raw_history]
    mapped_history = [_map_reading(record) for record in raw_history]

    return resolved_temp, resolved_humidity, simple_history, mapped_history

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global blockchain_service, sensor_registry, qr_service, freshness_classifier, shelf_life_predictor, marketplace_service
    blockchain_service = BlockchainService()
    await blockchain_service.initialize()

    sensor_registry = SensorRegistry(settings.SENSOR_STATE_PATH)
    qr_service = QRService(settings.QR_CACHE_DIR)
    freshness_classifier = FreshnessClassifier(settings.FRESHNESS_MODEL_PATH)

    try:
        shelf_life_predictor = ShelfLifePredictor(
            settings.SHELF_LIFE_MODEL_PATH,
            settings.SHELF_LIFE_HISTORY_PATH,
        )
    except FileNotFoundError as exc:
        logger.error("Unable to load shelf-life model: %s", exc)
        shelf_life_predictor = None

    marketplace_service = MarketplaceService(
        state_path=settings.MARKETPLACE_DATA_PATH,
        advance_percent=settings.MARKETPLACE_ADVANCE_PERCENT,
        razorpay_key_id=settings.RAZORPAY_KEY_ID,
        razorpay_key_secret=settings.RAZORPAY_KEY_SECRET,
    )

    yield
    # Shutdown hooks can be added here

app = FastAPI(
    title="FreshChain Backend API",
    description="Backend service for FreshChain dApp - handles blockchain operations",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "FreshChain Backend API", "status": "running"}

@app.get("/health")
async def health_check():
    try:
        is_connected = await blockchain_service.check_connection()
        return {
            "status": "healthy",
            "blockchain_connected": is_connected,
            "network": settings.NETWORK_NAME
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Service unhealthy: {str(e)}")

# Authentication Endpoints
@app.post("/auth/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """Login endpoint for all user types"""
    user = auth_service.authenticate_user(request.username, request.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Return username as token for demo (use JWT in production)
    return LoginResponse(
        success=True,
        token=user.username,
        user={
            "id": user.id,
            "username": user.username,
            "role": user.role.value,
            "wallet_address": user.wallet_address
        },
        message=f"Logged in as {user.role.value}"
    )

@app.get("/auth/me", response_model=UserInfo)
async def get_current_user_info(user: User = Depends(get_current_user)):
    """Get current user information"""
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    return UserInfo(
        id=user.id,
        username=user.username,
        role=user.role,
        wallet_address=user.wallet_address
    )

# Batch Management Endpoints
@app.post("/batch/create", response_model=SuccessResponse)
async def create_batch(request: CreateBatchRequest, user: User = Depends(require_admin_or_producer)):
    """Create a new batch on the blockchain (Admin or Retailer only)"""
    try:
        tx_hash = await blockchain_service.create_batch(
            batch_id=request.batchId,
            product_type=request.productType,
            created_by=user.username
        )
        return SuccessResponse(
            success=True,
            message="Batch created successfully",
            transactionHash=tx_hash
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create batch: {str(e)}")

@app.post("/batch/update-stage", response_model=SuccessResponse)
async def update_batch_stage(request: UpdateStageRequest, user: User = Depends(require_supply_chain_roles)):
    """Update batch stage/location on the blockchain (Retailer or Transporter only)"""
    try:
        # Validate stage progression
        current_batch = await blockchain_service.get_batch_details(request.batchId)
        if current_batch and current_batch.get('isFinalStage'):
            raise HTTPException(
                status_code=400, 
                detail="Cannot update batch - final selling stage reached"
            )
        
        # Validate stage transition based on user role
        if user.role == UserRole.TRANSPORTER and request.stage not in [BatchStage.IN_TRANSIT, BatchStage.AT_RETAILER]:
            raise HTTPException(
                status_code=403,
                detail="Transporters can only update to 'In Transit' or 'At Retailer' stages"
            )
        
        if user.role == UserRole.RETAILER and request.stage not in [BatchStage.AT_RETAILER, BatchStage.SELLING]:
            raise HTTPException(
                status_code=403,
                detail="Retailers can only update to 'At Retailer' or 'Selling' stages"
            )
        if user.role == UserRole.PRODUCER and request.stage not in [BatchStage.CREATED, BatchStage.HARVESTED]:
            raise HTTPException(
                status_code=403,
                detail="Producers can only move batches through creation and harvesting stages"
            )
        
        tx_hash = await blockchain_service.update_location(
            batch_id=request.batchId,
            stage=request.stage.value,
            location=request.location,
            updated_by=user.username
        )
        return SuccessResponse(
            success=True,
            message="Batch stage updated successfully",
            transactionHash=tx_hash
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update batch stage: {str(e)}")

@app.post("/batch/report-alert", response_model=SuccessResponse)
async def report_alert(request: ReportAlertRequest, user: User = Depends(require_retailer_or_transporter)):
    """Report an alert/excursion for a batch (Retailer or Transporter only)"""
    try:
        tx_hash = await blockchain_service.report_excursion(
            batch_id=request.batchId,
            alert_type=request.alertType,
            encrypted_data=request.encryptedData,
            reported_by=user.username
        )
        return SuccessResponse(
            success=True,
            message="Alert reported successfully",
            transactionHash=tx_hash
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to report alert: {str(e)}")

# Consumer Audit Endpoints (Public - no auth required for QR scanning)
@app.get("/batch/{batch_id}", response_model=BatchResponse)
async def get_batch_details(batch_id: str, user: User = Depends(get_current_user)):
    """Get batch details for consumer audit (QR scan) - Always returns latest blockchain state"""
    try:
        batch_data = await blockchain_service.get_batch_details(batch_id)
        if not batch_data:
            raise HTTPException(status_code=404, detail="Batch not found")
        
        return BatchResponse(**batch_data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch batch details: {str(e)}")


# Sensor + QR Workflows
@app.post("/sensors/register", response_model=SensorRegistrationResponse)
async def register_sensor_endpoint(
    request: SensorRegistrationRequest,
    user: User = Depends(require_supply_chain_roles),
):
    registry = _require_service(sensor_registry, "Sensor registry")

    # Enforce sensor type per role (except Admin who can register any type)
    if user.role == UserRole.TRANSPORTER and request.sensorType != SensorType.TRANSPORTER:
        raise HTTPException(status_code=400, detail="Transporters can only register transporter sensors")
    if user.role == UserRole.RETAILER and request.sensorType != SensorType.RETAILER:
        raise HTTPException(status_code=400, detail="Retailers can only register retailer sensors")

    payload = await registry.register_sensor(
        sensor_id=request.sensorId,
        sensor_type=request.sensorType,
        owner_username=user.username,
        label=request.label,
        vehicle_or_store_id=request.vehicleOrStoreId,
        metadata=request.metadata,
    )

    return SensorRegistrationResponse(
        success=True,
        sensorId=payload["sensorId"],
        sensorType=request.sensorType,
        label=payload.get("label"),
        vehicleOrStoreId=payload.get("vehicleOrStoreId"),
    )


@app.post("/sensors/data", response_model=SensorReadingResponse)
async def push_sensor_data(
    request: SensorReadingRequest,
    user: User = Depends(require_supply_chain_roles),
):
    registry = _require_service(sensor_registry, "Sensor registry")
    blockchain = _require_service(blockchain_service, "Blockchain service")
    captured_at = _datetime_to_iso(request.capturedAt) if request.capturedAt else None

    try:
        entry, sample_count = await registry.record_reading(
            sensor_id=request.sensorId,
            temperature=request.temperature,
            humidity=request.humidity,
            source=user.role.value,
            batch_id=request.batchId,
            captured_at=captured_at,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Check temperature thresholds and report ONLY violations to blockchain
    # Normal temperatures (2-10°C) are NOT reported to save blockchain costs
    temp = request.temperature
    if temp < settings.TEMP_MIN_THRESHOLD or temp > settings.TEMP_MAX_THRESHOLD:
        try:
            if temp < settings.TEMP_MIN_THRESHOLD:
                alert_type = "Temperature Too Low"
                alert_msg = f"CRITICAL: Temperature dropped to {temp}°C (below {settings.TEMP_MIN_THRESHOLD}°C threshold)"
            else:
                alert_type = "Temperature Too High"
                alert_msg = f"CRITICAL: Temperature rose to {temp}°C (above {settings.TEMP_MAX_THRESHOLD}°C threshold)"
            
            alert_msg += f" | Sensor: {request.sensorId} | Humidity: {request.humidity}%"
            
            await blockchain.report_alert(
                batch_id=request.batchId,
                alert_type=alert_type,
                encrypted_data=alert_msg,
                reporter=user.username
            )
            logger.info(f"Temperature threshold violation reported to blockchain for batch {request.batchId}")
        except Exception as e:
            logger.warning(f"Failed to report temperature threshold violation to blockchain: {e}")
    # If temperature is within normal range (2-10°C), no blockchain update is made

    history = await registry.get_batch_readings(entry["batchId"], limit=10)
    return SensorReadingResponse(
        batchId=entry["batchId"],
        samples=sample_count,
        latest=_map_reading(entry),
        history=[_map_reading(record) for record in history],
    )


@app.get("/sensors/batch/{batch_id}", response_model=SensorReadingResponse)
async def get_batch_sensor_history(batch_id: str, user: User = Depends(require_supply_chain_roles)):
    registry = _require_service(sensor_registry, "Sensor registry")
    history = await registry.get_batch_readings(batch_id, limit=20)
    mapped = [_map_reading(record) for record in history]
    latest = mapped[0] if mapped else None
    return SensorReadingResponse(batchId=batch_id, samples=len(history), latest=latest, history=mapped)


@app.get("/sensors/available", response_model=SensorListResponse)
async def list_available_sensors(
    sensorType: Optional[SensorType] = None,
    user: User = Depends(require_supply_chain_roles)
):
    """List all available sensors for the current user's role"""
    registry = _require_service(sensor_registry, "Sensor registry")
    
    # Filter by role type if specific sensor type requested
    if not sensorType:
        # Auto-detect based on user role
        if user.role == UserRole.TRANSPORTER:
            sensorType = SensorType.TRANSPORTER
        elif user.role == UserRole.RETAILER:
            sensorType = SensorType.RETAILER
    
    sensors = await registry.list_sensors(sensor_type=sensorType, owner=None)
    
    sensor_infos = [
        SensorInfo(
            sensorId=s["sensorId"],
            sensorType=SensorType(s["sensorType"]),
            label=s.get("label"),
            vehicleOrStoreId=s.get("vehicleOrStoreId"),
            owner=s["owner"],
            registeredAt=s["registeredAt"],
            isLinked=s.get("isLinked", False),
            currentBatch=s.get("currentBatch")
        )
        for s in sensors
    ]
    
    return SensorListResponse(sensors=sensor_infos)


@app.post("/qr/generate", response_model=QRCodeResponse)
async def generate_qr_code(request: QRCodeRequest, user: User = Depends(require_admin_or_producer)):
    qr_util = _require_service(qr_service, "QR service")
    qr = qr_util.generate(
        batch_id=request.batchId,
        stage=request.stage.value,
        metadata=request.metadata,
    )
    return QRCodeResponse(**qr)


@app.post("/qr/scan", response_model=QRScanResponse)
async def scan_qr_code(request: QRScanRequest, user: User = Depends(require_retailer_or_transporter)):
    registry = _require_service(sensor_registry, "Sensor registry")
    qr_util = _require_service(qr_service, "QR service")
    blockchain = _require_service(blockchain_service, "Blockchain service")

    if user.role == UserRole.TRANSPORTER and request.locationType != SensorType.TRANSPORTER:
        raise HTTPException(status_code=400, detail="Transporter can only link transporter sensors")
    if user.role == UserRole.RETAILER and request.locationType != SensorType.RETAILER:
        raise HTTPException(status_code=400, detail="Retailer can only link retailer sensors")

    sensor_meta = await registry.get_sensor(request.sensorId)
    if not sensor_meta:
        raise HTTPException(status_code=404, detail="Sensor is not registered")
    if sensor_meta.get("sensorType") != request.locationType.value:
        raise HTTPException(status_code=400, detail="Sensor type does not match requested location type")

    if request.qrPayload:
        decoded = qr_util.decode_payload(request.qrPayload)
        if decoded.get("batchId") != request.batchId:
            raise HTTPException(status_code=400, detail="QR payload does not match batch")

    try:
        await registry.link_sensor(
            sensor_id=request.sensorId,
            batch_id=request.batchId,
            location_type=request.locationType,
            linked_by=user.username,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Auto-update blockchain stage when scanned
    try:
        if user.role == UserRole.TRANSPORTER:
            new_stage = BatchStage.IN_TRANSIT
            location = "In Transit"
        elif user.role == UserRole.RETAILER:
            new_stage = BatchStage.AT_RETAILER
            location = "Retail Store"
        else:
            new_stage = None
        
        if new_stage:
            await blockchain.update_stage(
                batch_id=request.batchId,
                new_stage=new_stage,
                location=location,
                updated_by=user.username
            )
    except Exception as e:
        logger.warning(f"Failed to update blockchain stage for {request.batchId}: {e}")
        # Don't fail the sensor linking if blockchain update fails

    return QRScanResponse(
        success=True,
        batchId=request.batchId,
        sensorId=request.sensorId,
        locationType=request.locationType,
    )


@app.post("/ml/freshness-scan", response_model=FreshnessScanResponse)
async def freshness_scan(
    batchId: Optional[str] = Form(None),
    file: UploadFile = File(...),
    user: User = Depends(require_supply_chain_roles),
):
    classifier = _require_service(freshness_classifier, "Freshness classifier")
    blockchain = _require_service(blockchain_service, "Blockchain service")

    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Uploaded file must be an image")

    image_bytes = await file.read()
    try:
        prediction: FreshnessPrediction = classifier.predict(image_bytes)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Store freshness scan result on blockchain if batchId provided
    if batchId:
        try:
            # Check if freshness already recorded for this batch
            batch_details = await blockchain.get_batch(batchId)
            
            # Check if freshness scan alert already exists
            has_freshness_scan = any(
                alert.get("alertType") == "Freshness Scan"
                for alert in batch_details.get("alerts", [])
            )
            
            if not has_freshness_scan:
                # Store as blockchain alert (encrypted data)
                alert_data = (
                    f"AI Freshness Analysis: {prediction.category} "
                    f"(Score: {prediction.score:.2%}, Confidence: {prediction.confidence:.2%}). "
                    f"{prediction.message}"
                )
                
                await blockchain.report_alert(
                    batch_id=batchId,
                    alert_type="Freshness Scan",
                    encrypted_data=alert_data,
                    reporter=user.username
                )
        except Exception as e:
            logger.warning(f"Failed to store freshness scan on blockchain for {batchId}: {e}")
            # Don't fail the scan if blockchain storage fails

    return FreshnessScanResponse(
        batchId=batchId,
        freshnessScore=prediction.score,
        freshnessCategory=prediction.category,
        confidence=prediction.confidence,
        message=prediction.message,
        dominantClass=prediction.dominant_class,
        dominantScore=prediction.dominant_score,
    )


@app.post("/ml/shelf-life", response_model=ShelfLifePredictionResponse)
async def shelf_life_prediction(
    request: ShelfLifePredictionRequest,
    user: User = Depends(require_supply_chain_roles),
):
    predictor = _require_service(shelf_life_predictor, "Shelf-life predictor")

    temperature_c, humidity_percent, sensor_samples_raw, mapped_history = await _resolve_environmental_context(
        batch_id=request.batchId,
        temperature_override=request.averageTemperature,
        humidity_override=request.averageHumidity,
    )

    if temperature_c is None or humidity_percent is None:
        raise HTTPException(
            status_code=400,
            detail="No temperature/humidity data is available for this batch. Provide overrides or ingest sensor data first.",
        )

    try:
        result: ShelfLifeResult = predictor.predict(
            product_type=request.productType,
            temperature_c=temperature_c,
            humidity_percent=humidity_percent,
            sensor_readings=sensor_samples_raw,
            alpha_override=request.alphaOverride,
            batch_id=request.batchId,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return ShelfLifePredictionResponse(
        batchId=request.batchId,
        productType=request.productType,
        mlPredictionDays=result.ml_prediction,
        arrheniusPredictionDays=result.arrhenius_prediction,
        hybridPredictionDays=result.hybrid_prediction,
        alphaUsed=result.alpha_used,
        sensorTemperatureC=result.sensor_temperature,
        sensorHumidityPercent=result.sensor_humidity,
        sensorSamples=result.sensor_samples,
        metadata={
            "sensorStability": result.sensor_stability,
            "mlPerformance": result.ml_performance,
            "historySamples": [reading.dict() for reading in mapped_history[:5]],
        },
    )


# Marketplace + Payments
@app.post("/marketplace/parent", response_model=ParentOfferResponse)
async def create_parent_offer(
    request: ParentOfferRequest,
    user: User = Depends(require_producer),
):
    marketplace = _require_service(marketplace_service, "Marketplace")
    try:
        record = await marketplace.create_parent(producer=user.username, payload=request.dict())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return _map_parent_offer(record)


@app.get("/marketplace/parent", response_model=List[ParentOfferResponse])
async def list_parent_offers(
    status: Optional[str] = None,
    user: User = Depends(require_supply_chain_roles),
):
    marketplace = _require_service(marketplace_service, "Marketplace")
    role = user.role
    status_filter = status
    producer_filter = None

    if role == UserRole.RETAILER or role == UserRole.TRANSPORTER:
        status_filter = "published"
    elif role == UserRole.PRODUCER:
        producer_filter = user.username

    records = await marketplace.list_parents(status=status_filter, producer=producer_filter)
    return [_map_parent_offer(record) for record in records]


@app.post("/marketplace/parent/{parent_id}/publish", response_model=ParentOfferResponse)
async def publish_parent_offer(parent_id: str, user: User = Depends(require_producer)):
    marketplace = _require_service(marketplace_service, "Marketplace")
    try:
        record = await marketplace.publish_parent(parent_id, producer=user.username)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return _map_parent_offer(record)


@app.get("/marketplace/requests", response_model=List[MarketplaceRequestResponse])
async def list_marketplace_requests(
    parentId: Optional[str] = None,
    user: User = Depends(require_supply_chain_roles),
):
    marketplace = _require_service(marketplace_service, "Marketplace")

    retailer_filter = user.username if user.role == UserRole.RETAILER else None
    producer_filter = user.username if user.role == UserRole.PRODUCER else None

    records = await marketplace.list_requests(
        parent_id=parentId,
        retailer=retailer_filter,
        producer=producer_filter,
    )
    return [_map_marketplace_request(record) for record in records]


@app.post("/marketplace/requests", response_model=MarketplaceRequestResponse)
async def create_marketplace_request(
    request: RetailerBidRequest,
    user: User = Depends(require_retailer),
):
    marketplace = _require_service(marketplace_service, "Marketplace")
    try:
        record = await marketplace.create_request(
            parent_id=request.parentId,
            retailer=user.username,
            quantity=request.quantity,
            bid_price=request.bidPrice,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return _map_marketplace_request(record)


@app.post("/marketplace/requests/{request_id}/approve", response_model=MarketplaceRequestResponse)
async def approve_marketplace_request(
    request_id: str,
    user: User = Depends(require_producer),
):
    marketplace = _require_service(marketplace_service, "Marketplace")
    try:
        record = await marketplace.approve_request(request_id, producer=user.username)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return _map_marketplace_request(record)


@app.post("/marketplace/requests/{request_id}/reject", response_model=MarketplaceRequestResponse)
async def reject_marketplace_request(
    request_id: str,
    user: User = Depends(require_producer),
):
    marketplace = _require_service(marketplace_service, "Marketplace")
    try:
        record = await marketplace.reject_request(request_id, producer=user.username)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return _map_marketplace_request(record)


@app.post("/marketplace/requests/{request_id}/order", response_model=PaymentOrderResponse)
async def create_payment_order_for_request(
    request_id: str,
    user: User = Depends(require_retailer),
):
    marketplace = _require_service(marketplace_service, "Marketplace")
    existing = await marketplace.get_request(request_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Marketplace request not found")
    if existing["retailer"] != user.username:
        raise HTTPException(status_code=403, detail="You can only create payment orders for your own bids")

    try:
        result = await marketplace.create_payment_order(request_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    order = result["order"]
    return PaymentOrderResponse(
        orderId=order["id"],
        amount=result["advanceAmount"],
        currency=result["currency"],
        order=order,
    )


@app.post("/marketplace/requests/{request_id}/confirm", response_model=MarketplaceRequestResponse)
async def confirm_payment_for_request(
    request_id: str,
    request: PaymentConfirmationRequest,
    user: User = Depends(require_retailer),
):
    marketplace = _require_service(marketplace_service, "Marketplace")
    existing = await marketplace.get_request(request_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Marketplace request not found")
    if existing["retailer"] != user.username:
        raise HTTPException(status_code=403, detail="You can only confirm payment for your own bids")

    try:
        response = await marketplace.confirm_payment(
            request_id=request_id,
            payment_id=request.paymentId,
            order_id=request.orderId,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return _map_marketplace_request(response["request"])


@app.post("/marketplace/requests/{request_id}/fulfill", response_model=SuccessResponse)
async def fulfill_marketplace_request(
    request_id: str,
    payload: FulfillBidRequest,
    user: User = Depends(require_admin_or_producer),
):
    marketplace = _require_service(marketplace_service, "Marketplace")
    blockchain = _require_service(blockchain_service, "Blockchain")

    record = await marketplace.get_request(request_id)
    if not record:
        raise HTTPException(status_code=404, detail="Marketplace request not found")
    if record["status"] != "paid":
        raise HTTPException(status_code=400, detail="Request is not paid yet")

    parent = await marketplace.get_parent(record["parentId"])
    if not parent:
        raise HTTPException(status_code=404, detail="Parent offer not found")
    if parent["producer"] != user.username and user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Only the producer or admin can fulfill this request")

    existing_batch = await blockchain.get_batch_details(payload.childBatchId)
    if existing_batch:
        raise HTTPException(status_code=400, detail="Child batch ID already exists on-chain")

    product_type = payload.productType or parent["productType"]
    try:
        tx_hash = await blockchain.create_batch(
            batch_id=payload.childBatchId,
            product_type=product_type,
            created_by=user.username,
        )
    except Exception as exc:  # noqa: BLE001 - surface blockchain errors
        raise HTTPException(status_code=500, detail=f"Failed to mint child batch: {exc}") from exc

    try:
        await marketplace.mark_fulfilled(request_id, payload.childBatchId)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return SuccessResponse(
        success=True,
        message="Marketplace request fulfilled and child batch created",
        transactionHash=tx_hash,
    )

@app.get("/batches/by-stage")
async def get_batches_by_stage(
    stage: Optional[str] = None,
    user: User = Depends(require_supply_chain_roles)
):
    """Get all batches filtered by stage and current user responsibility"""
    try:
        all_batches = await blockchain_service.get_all_batches()
        
        # Filter by stage if provided
        if stage:
            filtered_batches = [b for b in all_batches if b.get("currentStage") == stage]
            return {"success": True, "data": filtered_batches}
        
        # For transporter: show only batches they are handling (last updatedBy = their username)
        if user.role == UserRole.TRANSPORTER:
            relevant_batches = [
                b for b in all_batches 
                if b.get("currentStage") in ["In Transit"]
                and b.get("locationHistory", [])
                and any(
                    loc.get("updatedBy") == user.username 
                    for loc in b.get("locationHistory", [])
                    if loc.get("stage") == "In Transit"
                )
            ]
            return {"success": True, "data": relevant_batches}
        
        # For retailer: show only batches they are handling
        if user.role == UserRole.RETAILER:
            relevant_batches = [
                b for b in all_batches 
                if b.get("currentStage") in ["At Retailer", "Selling"]
                and b.get("locationHistory", [])
                and any(
                    loc.get("updatedBy") == user.username 
                    for loc in b.get("locationHistory", [])
                    if loc.get("stage") in ["At Retailer", "Selling"]
                )
            ]
            return {"success": True, "data": relevant_batches}
        
        # For producer/admin: show all
        return {"success": True, "data": all_batches}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch batches: {str(e)}")


# Admin-only endpoints
@app.get("/admin/batches")
async def get_all_batches(user: User = Depends(require_admin)):
    """Get all batches (Admin only)"""
    try:
        batches = await blockchain_service.get_all_batches()
        return {"success": True, "data": batches}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch batches: {str(e)}")

@app.post("/admin/wallet/connect")
async def connect_admin_wallet(wallet_address: str, user: User = Depends(require_admin)):
    """Connect admin wallet address (Admin only)"""
    try:
        # Update user's wallet address
        user.wallet_address = wallet_address
        return {"success": True, "message": "Wallet connected successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to connect wallet: {str(e)}")


@app.get("/admin/wallet/status")
async def get_wallet_status(user: User = Depends(require_admin)):
    """Return basic wallet/network info for frontend MetaMask checks (Admin only)."""
    return {
        "connected": True,
        "network": settings.NETWORK_NAME,
        "chainId": hex(settings.CHAIN_ID),
        "requiredChainId": hex(settings.CHAIN_ID),
        "contractAddress": settings.CONTRACT_ADDRESS,
    }


@app.post("/admin/metamask/create-batch")
async def admin_create_batch_with_metamask(request: CreateBatchRequest, user: User = Depends(require_admin)):
    """Compatibility endpoint: Admin creates a batch via backend-only MetaMask flow."""
    svc = _require_service(blockchain_service, "Blockchain")

    try:
        # Prevent duplicates
        existing = await svc.get_batch_details(request.batchId)
        if existing:
            raise HTTPException(status_code=400, detail="Batch ID already exists")

        tx_hash = await svc.create_batch(
            batch_id=request.batchId,
            product_type=request.productType,
            created_by=user.username,
        )
        return {
            "success": True,
            "message": "Batch created successfully via admin MetaMask",
            "transactionHash": tx_hash,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to create batch: {exc}") from exc


@app.post("/admin/metamask/update-stage")
async def admin_update_stage_with_metamask(request: UpdateStageRequest, user: User = Depends(require_admin)):
    """Compatibility endpoint: Admin updates batch stage via backend-only MetaMask flow."""
    svc = _require_service(blockchain_service, "Blockchain")

    try:
        batch_data = await svc.get_batch_details(request.batchId)
        if not batch_data:
            raise HTTPException(status_code=404, detail="Batch not found")
        if batch_data.get("isFinalStage"):
            raise HTTPException(status_code=400, detail="Cannot update batch in final stage")

        tx_hash = await svc.update_location(
            batch_id=request.batchId,
            stage=request.stage.value,
            location=request.location,
            updated_by=user.username,
        )
        return {
            "success": True,
            "message": "Batch stage updated successfully via admin MetaMask",
            "transactionHash": tx_hash,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to update batch: {exc}") from exc

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )