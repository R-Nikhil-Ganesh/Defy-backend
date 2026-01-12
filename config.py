from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent


class Settings(BaseSettings):
    # Blockchain Configuration
    SHARDEUM_RPC_URL: str = "https://api-mezame.shardeum.org/"
    NETWORK_NAME: str = "Shardeum Testnet"
    CHAIN_ID: int = 8119
    
    # System Wallet (Admin/Backend wallet for all transactions)
    SYSTEM_PRIVATE_KEY: str = "your-private-key-here"
    
    # Smart Contract
    CONTRACT_ADDRESS: str = "0x064e8D53bFF8023b0531FE845195c3741790870E"
    CONTRACT_ABI_PATH: str = "contracts/FreshChain.json"
    
    # API Configuration
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    DEBUG: bool = True
    
    # Security
    SECRET_KEY: str = "your-secret-key-change-in-production"
    
    # Gas Configuration - Aggressively Optimized for Shardeum
    GAS_LIMIT: int = 150000  # Further reduced for cost efficiency
    GAS_PRICE_GWEI: Optional[int] = 1  # Ultra-low gas price for Shardeum testnet
    GAS_ESTIMATION_BUFFER: float = 1.15  # Reduced buffer from 1.2 to 1.15
    
    # Blockchain Explorer Configuration
    EXPLORER_BASE_URL: str = "https://explorer-mezame.shardeum.org"
    EXPLORER_TX_URL: str = "https://explorer-mezame.shardeum.org/tx"

    # Marketplace / Pricing Layer
    MARKETPLACE_DATA_PATH: str = str(BASE_DIR / "data" / "marketplace_state.json")
    MARKETPLACE_ADVANCE_PERCENT: float = 0.2  # 20% advance payment

    # Razorpay (test credentials by default)
    RAZORPAY_KEY_ID: str = "rzp_test_Rv8cTIJoSHbhQM"
    RAZORPAY_KEY_SECRET: str = "O1Lm58aNKCamcB2xbLgUe0WX"

    # Data / Model Assets
    DATA_DIR: str = str(BASE_DIR / "data")
    SENSOR_STATE_PATH: str = str(BASE_DIR / "data" / "sensor_state.json")
    QR_CACHE_DIR: str = str(BASE_DIR / "data" / "qr")
    
    # Temperature Monitoring Thresholds (Celsius)
    TEMP_MIN_THRESHOLD: float = 2.0  # Alert if temperature drops below 2°C
    TEMP_MAX_THRESHOLD: float = 10.0  # Alert if temperature exceeds 10°C
    FRESHNESS_MODEL_PATH: str = str(PROJECT_ROOT / "fruit-veg-freshness-ai-main" / "rottenvsfresh98pval.h5")
    FRESHNESS_CLASS_NAMES_PATH: Optional[str] = None
    SHELF_LIFE_MODEL_PATH: str = str(PROJECT_ROOT / "freshness" / "shelf_life_model.pkl")
    SHELF_LIFE_HISTORY_PATH: str = str(PROJECT_ROOT / "freshness" / "prediction_history.json")
    
    class Config:
        env_file = ".env"
        case_sensitive = True

# Global settings instance
settings = Settings()