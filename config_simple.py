import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Settings:
    # Blockchain Configuration
    SHARDEUM_RPC_URL = os.getenv("SHARDEUM_RPC_URL", "https://dapps.shardeum.org/")
    NETWORK_NAME = os.getenv("NETWORK_NAME", "Shardeum Testnet")
    CHAIN_ID = int(os.getenv("CHAIN_ID", "8081"))
    
    # System Wallet (Admin/Backend wallet for all transactions)
    SYSTEM_PRIVATE_KEY = os.getenv("SYSTEM_PRIVATE_KEY", "")
    
    # Smart Contract
    CONTRACT_ADDRESS = os.getenv("CONTRACT_ADDRESS", "")
    CONTRACT_ABI_PATH = os.getenv("CONTRACT_ABI_PATH", "contracts/FreshChain.json")
    
    # API Configuration
    API_HOST = os.getenv("API_HOST", "0.0.0.0")
    API_PORT = int(os.getenv("API_PORT", "8000"))
    DEBUG = os.getenv("DEBUG", "true").lower() == "true"
    
    # Security
    SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
    
    # Gas Configuration
    GAS_LIMIT = int(os.getenv("GAS_LIMIT", "500000"))
    GAS_PRICE_GWEI = os.getenv("GAS_PRICE_GWEI")
    if GAS_PRICE_GWEI:
        GAS_PRICE_GWEI = int(GAS_PRICE_GWEI)

# Global settings instance
settings = Settings()