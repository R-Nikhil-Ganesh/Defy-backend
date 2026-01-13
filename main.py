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
from services.product_ranges import check_conditions
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
        # Create batch on blockchain
        tx_hash = await blockchain_service.create_batch(
            batch_id=request.batchId,
            product_type=request.productType,
            created_by=user.username
        )
        
        # If sample image provided, process freshness test and store as alert
        if request.sampleImageBase64:
            try:
                # Run AI freshness analysis
                from services.ai_service import analyze_freshness
                analysis_result = await analyze_freshness(request.sampleImageBase64)
                
                # Store freshness scan result as blockchain alert
                alert_data = {
                    "type": "Freshness Scan",
                    "stage": "Producer",
                    "score": analysis_result.get("freshness_score", 0),
                    "category": analysis_result.get("category", "Unknown"),
                    "confidence": analysis_result.get("confidence", 0),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                
                # Encrypt and store alert
                encrypted_data = str(alert_data)  # In production, use proper encryption
                await blockchain_service.report_alert(
                    batch_id=request.batchId,
                    alert_type="Freshness Scan",
                    encrypted_data=encrypted_data,
                    reported_by=user.username
                )
            except Exception as e:
                logger.warning(f"Sample testing failed but batch created: {str(e)}")
        
        return SuccessResponse(
            success=True,
            message="Batch created successfully" + (" with sample test" if request.sampleImageBase64 else ""),
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
        
        # Calculate age and extract freshness data for consumers
        from datetime import datetime, timezone
        created_str = batch_data.get("created", "")
        age_in_days = 0
        age_in_hours = 0
        
        try:
            # Parse datetime and ensure it's in UTC
            if created_str.endswith("Z"):
                created_date = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
            else:
                created_date = datetime.fromisoformat(created_str)
                if created_date.tzinfo is None:
                    created_date = created_date.replace(tzinfo=timezone.utc)
            
            # Calculate age using UTC now
            now_utc = datetime.now(timezone.utc)
            age_seconds = (now_utc - created_date).total_seconds()
            age_in_days = age_seconds / 86400
            age_in_hours = age_seconds / 3600
            
            logger.info(f"Batch {batch_id} - Created: {created_date}, Now: {now_utc}, Age: {age_in_days:.2f} days / {age_in_hours:.2f} hours")
        except Exception as e:
            logger.error(f"Failed to calculate batch age: {e}")
            age_in_days = 0
            age_in_hours = 0
        
        # Extract freshness info from alerts (if available from manual scan)
        freshness_score = None
        freshness_category = None
        for alert in batch_data.get("alerts", []):
            if alert.get("alertType") == "Freshness Scan":
                encrypted_data = alert.get("encryptedData", "")
                # Parse: "AI Freshness Analysis: Fresh (Score: 95.50%, Confidence: 90%). Message"
                import re
                category_match = re.search(r"Analysis:\s+(\w+)", encrypted_data)
                score_match = re.search(r"Score:\s+([\d.]+)%", encrypted_data)
                if category_match:
                    freshness_category = category_match.group(1)
                if score_match:
                    freshness_score = float(score_match.group(1)) / 100.0
                break
        
        # Calculate freshness using hybrid approach (Arrhenius + ML) if no manual scan exists
        estimated_shelf_life_days = None
        if freshness_score is None:  # Calculate even for very young batches
            # Try with sensor data first
            if shelf_life_predictor:
                try:
                    logger.info(f"Attempting to calculate freshness for batch {batch_id} using hybrid model")
                    
                    # Get environmental conditions from sensor data
                    temperature_c, humidity_percent, _, _ = await _resolve_environmental_context(
                        batch_id=batch_id,
                        temperature_override=None,
                        humidity_override=None,
                    )
                    
                    logger.info(f"Batch {batch_id} - Temp: {temperature_c}°C, Humidity: {humidity_percent}%")
                    
                    if temperature_c and humidity_percent:
                        # Use hybrid model to predict shelf life
                        result: ShelfLifeResult = shelf_life_predictor.predict(
                            product_type=batch_data.get("productType", "Mixed"),
                            temperature_c=temperature_c,
                            humidity_percent=humidity_percent,
                        )
                        
                        estimated_shelf_life_days = result.hybrid_prediction
                        logger.info(
                            "Batch %s - Hybrid shelf life %.2f days (ML %.2f / Arrhenius %.2f, alpha %.2f)",
                            batch_id,
                            estimated_shelf_life_days,
                            result.ml_prediction,
                            result.arrhenius_prediction,
                            result.alpha_used,
                        )
                        
                        # Calculate freshness score based on age vs shelf life
                        # Freshness = 100% at age 0, decreases as age approaches shelf life
                        if estimated_shelf_life_days > 0:
                            freshness_ratio = max(0, 1 - (max(0, age_in_days) / estimated_shelf_life_days))
                            freshness_score = freshness_ratio
                            
                            # Determine category based on freshness score
                            if freshness_score >= 0.7:
                                freshness_category = "Fresh"
                            elif freshness_score >= 0.4:
                                freshness_category = "Moderate"
                            else:
                                freshness_category = "Poor"
                            
                            logger.info(f"Batch {batch_id} - Freshness: {freshness_score*100:.1f}% ({freshness_category})")
                    else:
                        logger.warning(f"Batch {batch_id} - No sensor data available")
                except Exception as e:
                    logger.error(f"Failed to calculate freshness using hybrid model: {e}", exc_info=True)
            
            # Fallback: Use standard shelf life for product type without sensor data
            if shelf_life_predictor and (freshness_score is None or estimated_shelf_life_days is None):
                try:
                    logger.info(f"Using fallback shelf life calculation for {batch_id} without sensor data")
                    # Use typical storage conditions: 4°C, 60% humidity
                    result: ShelfLifeResult = shelf_life_predictor.predict(
                        product_type=batch_data.get("productType", "Mixed"),
                        temperature_c=4.0,
                        humidity_percent=60.0,
                    )
                    
                    # Always set estimated shelf life
                    if estimated_shelf_life_days is None:
                        estimated_shelf_life_days = result.hybrid_prediction
                        logger.info(
                            "Batch %s - Fallback hybrid shelf life %.2f days (ML %.2f / Arrhenius %.2f, alpha %.2f)",
                            batch_id,
                            estimated_shelf_life_days,
                            result.ml_prediction,
                            result.arrhenius_prediction,
                            result.alpha_used,
                        )
                    
                    # Calculate freshness if not already set
                    if freshness_score is None and estimated_shelf_life_days and estimated_shelf_life_days > 0:
                        # Use age_in_hours for more precise calculation of very fresh batches
                        age_for_calc = age_in_hours / 24.0  # Convert to days
                        freshness_ratio = max(0, 1 - (max(0, age_for_calc) / estimated_shelf_life_days))
                        freshness_score = freshness_ratio
                        
                        if freshness_score >= 0.7:
                            freshness_category = "Fresh"
                        elif freshness_score >= 0.4:
                            freshness_category = "Moderate"
                        else:
                            freshness_category = "Poor"
                        
                        logger.info(f"Batch {batch_id} - Age: {age_for_calc:.4f} days, Shelf Life: {estimated_shelf_life_days:.2f} days, Freshness: {freshness_score*100:.1f}% ({freshness_category})")
                except Exception as e:
                    logger.error(f"Failed fallback freshness calculation: {e}", exc_info=True)
            
            # Ultimate fallback: Use product type defaults if model not available
            if freshness_score is None or estimated_shelf_life_days is None:
                logger.warning(f"Shelf life predictor not available, using product type defaults for {batch_id}")
                # Default shelf life by product type (in days at optimal storage)
                product_type = batch_data.get("productType", "Mixed").lower()
                default_shelf_lives = {
                    "apple": 30, "banana": 7, "tomato": 14, "grape": 7,
                    "orange": 21, "strawberry": 7, "lettuce": 7, "mixed": 14
                }
                
                # Find matching product type
                default_shelf_life = 14  # Default for unknown
                for key, days in default_shelf_lives.items():
                    if key in product_type:
                        default_shelf_life = days
                        break
                
                if estimated_shelf_life_days is None:
                    estimated_shelf_life_days = default_shelf_life
                    logger.info(f"Batch {batch_id} - Using default shelf life: {estimated_shelf_life_days} days")
                
                if freshness_score is None:
                    age_for_calc = age_in_hours / 24.0
                    freshness_ratio = max(0, 1 - (max(0, age_for_calc) / estimated_shelf_life_days))
                    freshness_score = freshness_ratio
                    
                    if freshness_score >= 0.7:
                        freshness_category = "Fresh"
                    elif freshness_score >= 0.4:
                        freshness_category = "Moderate"
                    else:
                        freshness_category = "Poor"
                    
                    logger.info(f"Batch {batch_id} - Default calculation: Age {age_for_calc:.4f}d, Shelf Life {estimated_shelf_life_days}d, Freshness {freshness_score*100:.1f}% ({freshness_category})")
        
        # Add computed fields
        batch_data["ageInDays"] = round(max(0, age_in_days), 2)
        batch_data["ageInHours"] = round(max(0, age_in_hours), 2)
        batch_data["estimatedShelfLifeDays"] = round(estimated_shelf_life_days, 2) if estimated_shelf_life_days else None
        batch_data["freshnessScore"] = freshness_score
        batch_data["freshnessCategory"] = freshness_category
        
        return BatchResponse(**batch_data)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch batch details: {str(e)}", exc_info=True)
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

    # Use the resolved batch ID from the entry (auto-detected from sensor linkage)
    resolved_batch_id = entry["batchId"]

    # Check 30-second average against thresholds (not individual readings)
    # This prevents false alarms from temporary fluctuations
    try:
        # Get batch details to determine product type
        batch_details = await blockchain.get_batch_details(resolved_batch_id)
        
        if batch_details:
            product_type = batch_details.get("productType", "").lower()
            
            # Get readings from last 30 seconds (for testing - change to 30 minutes for production)
            recent_readings = await registry.get_recent_readings_for_average(resolved_batch_id, minutes=0.5)
            
            # Need at least 2 readings (20 seconds worth at 10s intervals) to calculate average
            if len(recent_readings) >= 2:
                # Calculate 30-second averages
                avg_temp = sum(r["temperature"] for r in recent_readings) / len(recent_readings)
                avg_humidity = sum(r["humidity"] for r in recent_readings) / len(recent_readings)
                
                logger.info(f"Batch {resolved_batch_id}: 30-sec avg = {avg_temp:.2f}°C, {avg_humidity:.2f}% (based on {len(recent_readings)} readings)")
                
                # Check if 30-minute AVERAGE is within acceptable ranges
                condition_check = check_conditions(product_type, avg_temp, avg_humidity)
                
                # If there are violations in the average, report to blockchain
                if condition_check["violations"]:
                    alert_type = "Environmental Conditions Violation (30-sec Average)"
                    violation_details = " | ".join(condition_check["violations"])
                    
                    # DETAILED LOGGING FOR VIOLATIONS
                    logger.warning("=" * 80)
                    logger.warning("🚨 ENVIRONMENTAL VIOLATION DETECTED 🚨")
                    logger.warning("=" * 80)
                    logger.warning(f"Batch ID: {resolved_batch_id}")
                    logger.warning(f"Product Type: {product_type.capitalize()}")
                    logger.warning(f"Sensor ID: {request.sensorId}")
                    logger.warning(f"Reported By: {user.username}")
                    logger.warning(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
                    logger.warning("-" * 80)
                    logger.warning(f"30-Second Average Temperature: {avg_temp:.2f}°C")
                    logger.warning(f"30-Second Average Humidity: {avg_humidity:.2f}%")
                    logger.warning(f"Based on {len(recent_readings)} readings over 30 seconds")
                    logger.warning("-" * 80)
                    
                    if condition_check.get("ranges"):
                        ranges = condition_check["ranges"]
                        logger.warning(f"Expected Temperature Range: {ranges['temperature']['min']}°C to {ranges['temperature']['max']}°C")
                        logger.warning(f"Expected Humidity Range: {ranges['humidity']['min']}% to {ranges['humidity']['max']}%")
                        logger.warning("-" * 80)
                    
                    logger.warning("VIOLATIONS:")
                    for violation in condition_check["violations"]:
                        logger.warning(f"  ❌ {violation}")
                    logger.warning("-" * 80)
                    logger.warning("✅ Storing violation to BLOCKCHAIN...")
                    
                    alert_msg = f"CRITICAL: {violation_details}"
                    alert_msg += f" | Product: {product_type.capitalize()}"
                    alert_msg += f" | Sensor: {request.sensorId}"
                    alert_msg += f" | Based on {len(recent_readings)} readings over 30 seconds"
                    
                    if condition_check.get("ranges"):
                        ranges = condition_check["ranges"]
                        alert_msg += f" | Expected Temp: {ranges['temperature']['min']}°C to {ranges['temperature']['max']}°C"
                        alert_msg += f" | Expected Humidity: {ranges['humidity']['min']}% to {ranges['humidity']['max']}%"
                    
                    await blockchain.report_excursion(
                        batch_id=resolved_batch_id,
                        alert_type=alert_type,
                        encrypted_data=alert_msg,
                        reported_by=user.username
                    )
                    logger.warning("✅ Violation successfully stored in blockchain!")
                    logger.warning("=" * 80)
                else:
                    logger.info(f"Batch {resolved_batch_id}: 30-sec average within acceptable range")
            else:
                logger.info(f"Batch {resolved_batch_id}: Not enough readings yet ({len(recent_readings)}/2) for 30-sec average check")
        else:
            logger.warning(f"Batch {resolved_batch_id} not found, skipping threshold check")
    except Exception as e:
        logger.error(f"Failed to check thresholds or report to blockchain: {e}")
    # All sensor readings are stored locally, blockchain only receives 30-sec average violations

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


@app.get("/sensors/{sensor_id}/binding")
async def get_sensor_binding(sensor_id: str, user: User = Depends(require_supply_chain_roles)):
    """Get the batch that a sensor is currently linked to"""
    registry = _require_service(sensor_registry, "Sensor registry")
    binding = await registry.get_sensor_binding(sensor_id)
    
    if not binding:
        raise HTTPException(status_code=404, detail="Sensor not linked to any batch")
    
    return {
        "sensorId": sensor_id,
        "batchId": binding.get("batchId"),
        "locationType": binding.get("locationType"),
        "linkedAt": binding.get("linkedAt"),
        "linkedBy": binding.get("linkedBy")
    }


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
    classifier = _require_service(freshness_classifier, "Freshness classifier")

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

    # Mandatory sample testing: Process freshness scan if provided
    freshness_score = None
    freshness_category = None
    
    if request.sampleImageBase64:
        try:
            import base64
            image_bytes = base64.b64decode(request.sampleImageBase64)
            prediction: FreshnessPrediction = classifier.predict(image_bytes)
            freshness_score = prediction.score
            freshness_category = prediction.category
            
            # Store freshness scan on blockchain
            try:
                batch_details = await blockchain.get_batch(request.batchId)
                has_freshness_scan = any(
                    alert.get("alertType") == "Freshness Scan"
                    for alert in batch_details.get("alerts", [])
                )
                
                if not has_freshness_scan:
                    alert_data = (
                        f"AI Freshness Analysis: {prediction.category} "
                        f"(Score: {prediction.score:.2%}, Confidence: {prediction.confidence:.2%}). "
                        f"{prediction.message}"
                    )
                    await blockchain.report_excursion(
                        batch_id=request.batchId,
                        alert_type="Freshness Scan",
                        encrypted_data=alert_data,
                        reported_by=user.username
                    )
            except Exception as e:
                logger.warning(f"Failed to store freshness scan on blockchain: {e}")
        except Exception as e:
            logger.error(f"Failed to process sample image: {e}")
            raise HTTPException(status_code=400, detail=f"Invalid sample image: {str(e)}")

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
            new_stage = "In Transit"
            location = "In Transit"
        elif user.role == UserRole.RETAILER:
            new_stage = "At Retailer"
            location = "Retail Store"
        else:
            new_stage = None
        
        if new_stage:
            await blockchain.update_location(
                batch_id=request.batchId,
                stage=new_stage,
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
        sampleTestingRequired=not bool(request.sampleImageBase64),  # Warn if no sample provided
        freshnessScore=freshness_score,
        freshnessCategory=freshness_category,
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
                
                await blockchain.report_excursion(
                    batch_id=batchId,
                    alert_type="Freshness Scan",
                    encrypted_data=alert_data,
                    reported_by=user.username
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
    """Get all batches filtered by stage and current user responsibility - Optimized"""
    try:
        all_batches = await blockchain_service.get_all_batches()
        
        # Filter by stage if provided
        if stage:
            filtered_batches = [b for b in all_batches if b.get("currentStage") == stage]
            return {"success": True, "data": filtered_batches}
        
        # For transporter: show only In Transit batches
        if user.role == UserRole.TRANSPORTER:
            relevant_batches = [
                b for b in all_batches 
                if b.get("currentStage") == "In Transit"
            ]
            return {"success": True, "data": relevant_batches}
        
        # For retailer: show only At Retailer batches
        if user.role == UserRole.RETAILER:
            relevant_batches = [
                b for b in all_batches 
                if b.get("currentStage") == "At Retailer"
            ]
            return {"success": True, "data": relevant_batches}
        
        # For producer: show batches they created
        if user.role == UserRole.PRODUCER:
            relevant_batches = [
                b for b in all_batches 
                if b.get("currentStage") in ["Created", "Harvested"]
            ]
            return {"success": True, "data": relevant_batches}
        
        # Default: return all batches
        return {"success": True, "data": all_batches}
        
    except Exception as e:
        logger.error(f"Error getting batches by stage: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
        
        # If sample image provided, process freshness test and store as alert
        if request.sampleImageBase64:
            try:
                from services.ai_service import analyze_freshness
                analysis_result = await analyze_freshness(request.sampleImageBase64)
                
                alert_data = {
                    "type": "Freshness Scan",
                    "stage": "Producer",
                    "score": analysis_result.get("freshness_score", 0),
                    "category": analysis_result.get("category", "Unknown"),
                    "confidence": analysis_result.get("confidence", 0),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                
                encrypted_data = str(alert_data)
                await svc.report_alert(
                    batch_id=request.batchId,
                    alert_type="Freshness Scan",
                    encrypted_data=encrypted_data,
                    reported_by=user.username
                )
            except Exception as e:
                logger.warning(f"Sample testing failed but batch created: {str(e)}")
        
        return {
            "success": True,
            "message": "Batch created successfully via admin MetaMask" + (" with sample test" if request.sampleImageBase64 else ""),
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