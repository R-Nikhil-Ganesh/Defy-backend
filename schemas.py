from pydantic import BaseModel, Field
from typing import List, Optional, Any, Dict
from datetime import datetime
from enum import Enum

class BatchStage(str, Enum):
    CREATED = "Created"
    HARVESTED = "Harvested"
    IN_TRANSIT = "In Transit"
    AT_RETAILER = "At Retailer"
    SELLING = "Selling"  # Final stage

class UserRole(str, Enum):
    ADMIN = "admin"
    PRODUCER = "producer"
    RETAILER = "retailer"
    TRANSPORTER = "transporter"
    CONSUMER = "consumer"


class SensorType(str, Enum):
    TRANSPORTER = "transporter"
    RETAILER = "retailer"

class TemperatureStatus(str, Enum):
    NORMAL = "Normal"
    TOO_LOW = "Too Low"
    TOO_HIGH = "Too High"

# Authentication Models
class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    success: bool
    token: str
    user: dict
    message: str

class UserInfo(BaseModel):
    id: str
    username: str
    role: UserRole
    wallet_address: Optional[str] = None

# Request Models
class CreateBatchRequest(BaseModel):
    batchId: str = Field(..., description="Unique batch identifier")
    productType: str = Field(..., description="Type of product in the batch")
    sampleImageBase64: Optional[str] = Field(None, description="Base64 encoded sample image for freshness testing")
    freshnessScore: Optional[float] = Field(None, description="AI freshness score (0-100)")
    freshnessCategory: Optional[str] = Field(None, description="Freshness category (Fresh/Moderate/Rotten)")

class UpdateStageRequest(BaseModel):
    batchId: str = Field(..., description="Batch identifier")
    stage: BatchStage = Field(..., description="New stage")
    location: str = Field(..., description="Current location")

class ReportAlertRequest(BaseModel):
    batchId: str = Field(..., description="Batch identifier")
    alertType: str = Field(..., description="Type of alert/excursion")
    encryptedData: str = Field(..., description="Encrypted alert data (INCO)")

# Response Models
class SuccessResponse(BaseModel):
    success: bool = True
    message: str
    transactionHash: Optional[str] = None

class LocationUpdate(BaseModel):
    stage: BatchStage
    location: str
    timestamp: datetime
    transactionHash: str
    updatedBy: str  # User who made the update

class Alert(BaseModel):
    alertType: str
    encryptedData: str
    timestamp: datetime
    transactionHash: str

class BatchResponse(BaseModel):
    batchId: str
    productType: str
    created: datetime
    currentStage: BatchStage
    currentLocation: str
    locationHistory: List[LocationUpdate]
    alerts: List[Alert]
    isActive: bool
    isFinalStage: bool  # True when stage is SELLING
    # Time and freshness data for consumers
    ageInDays: Optional[float] = None
    ageInHours: Optional[float] = None
    estimatedShelfLifeDays: Optional[float] = None
    freshnessScore: Optional[float] = None
    freshnessCategory: Optional[str] = None

# Error Response
class ErrorResponse(BaseModel):
    success: bool = False
    error: str
    details: Optional[str] = None


# Sensor + QR Models
class SensorRegistrationRequest(BaseModel):
    sensorId: str = Field(..., description="Unique hardware identifier")
    sensorType: SensorType
    label: Optional[str] = None
    vehicleOrStoreId: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class SensorRegistrationResponse(BaseModel):
    success: bool
    sensorId: str
    sensorType: SensorType
    label: Optional[str] = None
    vehicleOrStoreId: Optional[str] = None


class SensorReadingRequest(BaseModel):
    sensorId: str
    temperature: float
    humidity: float
    batchId: Optional[str] = Field(None, description="Optional override when sensor not linked")
    capturedAt: Optional[datetime] = None


class SensorReading(BaseModel):
    batchId: str
    sensorId: str
    sensorType: SensorType
    temperature: float
    humidity: float
    capturedAt: datetime
    source: str
    temperatureStatus: Optional[str] = "Normal"  # "Normal", "Too Low", or "Too High"


class SensorReadingResponse(BaseModel):
    batchId: str
    samples: int
    latest: Optional[SensorReading] = None
    history: List[SensorReading] = Field(default_factory=list)

class SensorInfo(BaseModel):
    sensorId: str
    sensorType: SensorType
    label: Optional[str] = None
    vehicleOrStoreId: Optional[str] = None
    owner: str
    registeredAt: str
    isLinked: bool = False
    currentBatch: Optional[str] = None

class SensorListResponse(BaseModel):
    sensors: List[SensorInfo]


class QRCodeRequest(BaseModel):
    batchId: str
    stage: BatchStage
    metadata: Optional[Dict[str, Any]] = None


class QRCodeResponse(BaseModel):
    batchId: str
    payload: str
    qrImageBase64: str


class QRScanRequest(BaseModel):
    batchId: str
    sensorId: str
    locationType: SensorType
    qrPayload: Optional[str] = None
    # Mandatory sample testing fields
    sampleImageBase64: Optional[str] = None  # Base64 encoded image for freshness scan
    freshnessScore: Optional[float] = None
    freshnessCategory: Optional[str] = None


class QRScanResponse(BaseModel):
    success: bool
    batchId: str
    sensorId: str
    locationType: SensorType
    sampleTestingRequired: bool = False  # Indicates if sample testing was mandatory but missing
    freshnessScore: Optional[float] = None
    freshnessCategory: Optional[str] = None


# ML / Analytics Models
class FreshnessScanResponse(BaseModel):
    batchId: Optional[str]
    freshnessScore: float
    freshnessCategory: str
    confidence: float
    message: str
    dominantClass: Optional[str] = None
    dominantScore: Optional[float] = None


class ShelfLifePredictionRequest(BaseModel):
    batchId: str
    productType: str
    averageTemperature: Optional[float] = None
    averageHumidity: Optional[float] = None
    alphaOverride: Optional[float] = Field(None, ge=0.0, le=1.0)


class ShelfLifePredictionResponse(BaseModel):
    batchId: str
    productType: str
    mlPredictionDays: float
    arrheniusPredictionDays: float
    hybridPredictionDays: float
    alphaUsed: float
    sensorTemperatureC: float
    sensorHumidityPercent: float
    sensorSamples: int
    metadata: Optional[Dict[str, Any]] = None


# Marketplace Models
class ParentOfferRequest(BaseModel):
    productType: str
    unit: str = Field(..., description="Unit of measurement, e.g., kg")
    basePrice: float = Field(..., gt=0)
    totalQuantity: float = Field(..., gt=0)
    currency: str = Field("INR", description="Pricing currency")
    metadata: Optional[Dict[str, Any]] = None


class ParentOfferResponse(BaseModel):
    parentId: str
    parentBatchNumber: str
    producer: str
    productType: str
    unit: str
    basePrice: float
    totalQuantity: float
    availableQuantity: float
    pricingCurrency: str
    createdAt: datetime
    status: str
    publishedAt: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None


class RetailerBidRequest(BaseModel):
    parentId: str
    quantity: float = Field(..., gt=0)
    bidPrice: float = Field(..., gt=0)


class MarketplacePaymentInfo(BaseModel):
    orderId: str
    amount: int
    currency: str
    status: str
    createdAt: datetime
    paymentId: Optional[str] = None
    paidAt: Optional[datetime] = None


class MarketplaceRequestResponse(BaseModel):
    requestId: str
    parentId: str
    parentBatchNumber: Optional[str] = None
    parentProductType: Optional[str] = None
    retailer: str
    producer: Optional[str] = None
    quantity: float
    bidPrice: float
    status: str
    createdAt: datetime
    approvedAt: Optional[datetime] = None
    currency: str
    advancePercent: float
    payment: Optional[MarketplacePaymentInfo] = None
    childBatchId: Optional[str] = None
    fulfilledAt: Optional[datetime] = None


class PaymentOrderResponse(BaseModel):
    orderId: str
    amount: int
    currency: str
    order: Dict[str, Any]


class PaymentConfirmationRequest(BaseModel):
    paymentId: str
    orderId: str


class FulfillBidRequest(BaseModel):
    childBatchId: str
    productType: Optional[str] = None