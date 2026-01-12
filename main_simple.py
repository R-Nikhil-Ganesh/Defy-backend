#!/usr/bin/env python3
"""
FreshChain Backend - Production Mode
FastAPI server with real blockchain integration
"""
import sys
import os

# Ensure we can import from current directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    import uvicorn
except ImportError as e:
    print(f"❌ Missing dependency: {e}")
    print("Installing required packages...")
    import subprocess
    subprocess.run([
        sys.executable, "-m", "pip", "install", 
        "fastapi==0.103.2", 
        "uvicorn==0.23.2"
    ], check=True)
    print("✅ Packages installed! Please run again.")
    sys.exit(0)

from datetime import datetime
from typing import Dict, Any, Optional
import asyncio
import logging

# Import utilities
from utils import is_valid_transaction_hash, generate_explorer_url, is_real_transaction_hash

# Import blockchain service
try:
    from blockchain import BlockchainService
    BLOCKCHAIN_AVAILABLE = True
except ImportError:
    print("⚠️ Blockchain dependencies not available. Running in demo mode.")
    BLOCKCHAIN_AVAILABLE = False
    BlockchainService = None

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# In-memory storage for batches (fallback when blockchain is not available)
batches_storage = {}

# Real users for authentication (in production, use a proper user database)
users_db = {
    "admin": {"id": "1", "username": "admin", "role": "admin", "password": "admin123"},
    "aggregator": {"id": "2", "username": "aggregator", "role": "aggregator", "password": "aggregator123"},
    "retailer": {"id": "3", "username": "retailer", "role": "retailer", "password": "retailer123"},
    "transporter": {"id": "4", "username": "transporter", "role": "transporter", "password": "transporter123"},
    "consumer": {"id": "5", "username": "consumer", "role": "consumer", "password": "consumer123"},
}

app = FastAPI(
    title="FreshChain Backend API",
    description="Production backend service for FreshChain dApp with real blockchain integration",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000", 
        "http://127.0.0.1:3000",
        "http://localhost:3001", 
        "http://127.0.0.1:3001",
        "http://localhost:3002", 
        "http://127.0.0.1:3002"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global blockchain service instance
blockchain_service: Optional['BlockchainService'] = None

@app.on_event("startup")
async def startup_event():
    """Initialize blockchain service on startup"""
    global blockchain_service
    
    if BLOCKCHAIN_AVAILABLE and BlockchainService:
        try:
            blockchain_service = BlockchainService()
            await blockchain_service.initialize()
            logger.info("✅ Blockchain service initialized successfully")
            logger.info(f"System wallet: {blockchain_service.system_account.address}")
            logger.info(f"Contract address: {blockchain_service.contract.address}")
        except Exception as e:
            logger.error(f"❌ Failed to initialize blockchain service: {e}")
            logger.info("🔄 Falling back to demo mode")
            blockchain_service = None
    else:
        logger.info("🔄 Running in demo mode - blockchain not available")
    
    logger.info("✅ Backend initialization complete")

@app.get("/")
async def root():
    return {"message": "FreshChain Backend API", "status": "running"}

@app.get("/health")
async def health_check():
    blockchain_connected = False
    if blockchain_service:
        blockchain_connected = await blockchain_service.check_connection()
    
    return {
        "status": "healthy",
        "blockchain_connected": blockchain_connected,
        "network": "Shardeum Testnet" if blockchain_connected else "Demo Mode",
        "contract_address": "0x064e8D53bFF8023b0531FE845195c3741790870E" if blockchain_connected else None,
        "chain_id": 8119 if blockchain_connected else None
    }

@app.post("/auth/login")
async def login(request: dict):
    username = request.get("username")
    password = request.get("password")
    wallet_address = request.get("walletAddress")  # For admin MetaMask login
    
    if username in users_db:
        user = users_db[username]
        
        # Check password
        if user["password"] != password:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        # For admin, require wallet address
        if user["role"] == "admin":
            if not wallet_address:
                raise HTTPException(status_code=400, detail="Admin requires MetaMask wallet connection")
            user["wallet_address"] = wallet_address
        
        # Return user without password
        user_response = {k: v for k, v in user.items() if k != "password"}
        
        return {
            "success": True,
            "token": username,
            "user": user_response,
            "message": f"Logged in as {user['role']}"
        }
    
    raise HTTPException(status_code=401, detail="Invalid credentials")

@app.get("/auth/me")
async def get_current_user_info():
    return {
        "id": "1",
        "username": "demo_user",
        "role": "admin"
    }

@app.post("/batch/create")
async def create_batch(request: dict):
    batch_id = request.get("batchId")
    product_type = request.get("productType")
    
    if not batch_id or not product_type:
        raise HTTPException(status_code=400, detail="batchId and productType required")
    
    # Check if batch already exists
    if blockchain_service:
        existing_batch = await blockchain_service.get_batch_details(batch_id)
        if existing_batch:
            raise HTTPException(status_code=400, detail="Batch ID already exists")
    elif batch_id in batches_storage:
        raise HTTPException(status_code=400, detail="Batch ID already exists")
    
    try:
        if blockchain_service:
            # Use blockchain
            tx_hash = await blockchain_service.create_batch(batch_id, product_type, "system")
            return {
                "success": True,
                "message": "Batch created successfully on blockchain",
                "transactionHash": tx_hash
            }
        else:
            # Fallback to in-memory storage
            batch = {
                "batchId": batch_id,
                "productType": product_type,
                "created": datetime.now().isoformat() + "Z",
                "currentStage": "Created",
                "currentLocation": "Origin Farm",
                "locationHistory": [
                    {
                        "stage": "Created",
                        "location": "Origin Farm",
                        "timestamp": datetime.now().isoformat() + "Z",
                        "transactionHash": f"DEMO-{hash(batch_id + str(datetime.now().timestamp())) % 0xffffffffffffffff:016x}",
                        "updatedBy": "system"
                    }
                ],
                "alerts": [],
                "isActive": True,
                "isFinalStage": False
            }
            
            batches_storage[batch_id] = batch
            
            return {
                "success": True,
                "message": "Batch created successfully (demo mode)",
                "transactionHash": f"DEMO-{hash(batch_id + str(datetime.now().timestamp())) % 0xffffffffffffffff:016x}"
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create batch: {str(e)}")

@app.post("/batch/update-stage")
async def update_batch_stage(request: dict):
    batch_id = request.get("batchId")
    stage = request.get("stage")
    location = request.get("location")
    
    if not batch_id or not stage or not location:
        raise HTTPException(status_code=400, detail="batchId, stage, and location required")
    
    try:
        if blockchain_service:
            # Check if batch exists and get current state
            batch_data = await blockchain_service.get_batch_details(batch_id)
            if not batch_data:
                raise HTTPException(status_code=404, detail="Batch not found")
            
            if batch_data["isFinalStage"]:
                raise HTTPException(status_code=400, detail="Cannot update batch in final stage")
            
            # Update on blockchain
            tx_hash = await blockchain_service.update_location(batch_id, stage, location, "system")
            
            return {
                "success": True,
                "message": "Batch stage updated successfully on blockchain",
                "transactionHash": tx_hash
            }
        else:
            # Fallback to in-memory storage
            if batch_id not in batches_storage:
                raise HTTPException(status_code=404, detail="Batch not found")
            
            batch = batches_storage[batch_id]
            
            if batch["isFinalStage"]:
                raise HTTPException(status_code=400, detail="Cannot update batch in final stage")
            
            # Update batch
            batch["currentStage"] = stage
            batch["currentLocation"] = location
            batch["isFinalStage"] = (stage == "Selling")
            
            # Add to history
            batch["locationHistory"].insert(0, {
                "stage": stage,
                "location": location,
                "timestamp": datetime.now().isoformat() + "Z",
                "transactionHash": f"DEMO-{hash(batch_id + stage + str(datetime.now().timestamp())) % 0xffffffffffffffff:016x}",
                "updatedBy": "system"
            })
            
            return {
                "success": True,
                "message": "Batch stage updated successfully (demo mode)",
                "transactionHash": f"DEMO-{hash(batch_id + stage + str(datetime.now().timestamp())) % 0xffffffffffffffff:016x}"
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update batch: {str(e)}")

@app.post("/batch/report-alert")
async def report_alert(request: dict):
    batch_id = request.get("batchId")
    alert_type = request.get("alertType")
    encrypted_data = request.get("encryptedData")
    
    if not batch_id or not alert_type:
        raise HTTPException(status_code=400, detail="batchId and alertType required")
    
    try:
        if blockchain_service:
            # Use blockchain to report alert
            tx_hash = await blockchain_service.report_excursion(batch_id, alert_type, encrypted_data or "", "system")
            return {
                "success": True,
                "message": "Alert reported successfully on blockchain",
                "transactionHash": tx_hash
            }
        else:
            # Fallback to in-memory storage
            if batch_id not in batches_storage:
                raise HTTPException(status_code=404, detail="Batch not found")
            
            batch = batches_storage[batch_id]
            
            # Add alert with realistic transaction hash
            tx_hash = f"DEMO-{hash(batch_id + alert_type + str(datetime.now().timestamp())) % 0xffffffffffffffff:016x}"
            batch["alerts"].append({
                "alertType": alert_type,
                "encryptedData": encrypted_data or "",
                "timestamp": datetime.now().isoformat() + "Z",
                "transactionHash": tx_hash
            })
            
            return {
                "success": True,
                "message": "Alert reported successfully (demo mode)",
                "transactionHash": tx_hash
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to report alert: {str(e)}")

@app.get("/batch/{batch_id}")
async def get_batch_details(batch_id: str):
    try:
        if blockchain_service:
            # Get from blockchain - always returns latest state
            batch_data = await blockchain_service.get_batch_details(batch_id)
            if not batch_data:
                raise HTTPException(status_code=404, detail="Batch not found")
            
            # Convert datetime to ISO string for JSON serialization
            if isinstance(batch_data.get("created"), datetime):
                batch_data["created"] = batch_data["created"].isoformat() + "Z"
            
            return batch_data
        else:
            # Fallback to in-memory storage
            if batch_id not in batches_storage:
                raise HTTPException(status_code=404, detail="Batch not found")
            
            return batches_storage[batch_id]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get batch details: {str(e)}")

@app.get("/admin/batches")
async def get_all_batches():
    try:
        if blockchain_service:
            # Get from blockchain
            batches = await blockchain_service.get_all_batches()
            return {"success": True, "data": batches}
        else:
            # Fallback to in-memory storage
            return {"success": True, "data": list(batches_storage.values())}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get batches: {str(e)}")

@app.get("/admin/wallet/status")
async def get_wallet_status():
    """Get wallet connection status"""
    return {
        "connected": True,
        "network": "Shardeum Testnet",
        "chainId": "0x1fb7",  # 8119 in hex
        "requiredChainId": "0x1fb7",
        "contractAddress": "0x064e8D53bFF8023b0531FE845195c3741790870E"
    }

@app.get("/explorer/tx/{tx_hash}")
async def get_explorer_url(tx_hash: str):
    """Get explorer URL for a transaction hash"""
    try:
        if is_real_transaction_hash(tx_hash):
            explorer_url = generate_explorer_url(tx_hash)
            return {
                "success": True,
                "explorerUrl": explorer_url,
                "isReal": True,
                "network": "Shardeum Testnet"
            }
        else:
            return {
                "success": False,
                "error": "Demo transaction hash - not available on blockchain explorer",
                "isReal": False,
                "network": "Demo Mode"
            }
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to generate explorer URL: {str(e)}",
            "isReal": False
        }

# Admin MetaMask endpoints (simplified - backend handles all transactions)
@app.post("/admin/metamask/create-batch")
async def admin_create_batch_with_metamask(request: dict):
    """Admin creates batch - backend handles MetaMask transaction internally"""
    batch_id = request.get("batchId")
    product_type = request.get("productType")
    
    if not batch_id or not product_type:
        raise HTTPException(status_code=400, detail="batchId and productType required")
    
    try:
        if blockchain_service:
            # Check if batch already exists
            existing_batch = await blockchain_service.get_batch_details(batch_id)
            if existing_batch:
                raise HTTPException(status_code=400, detail="Batch ID already exists")
            
            # Create batch on blockchain using system wallet
            tx_hash = await blockchain_service.create_batch(batch_id, product_type, "admin")
            
            return {
                "success": True,
                "message": "Batch created successfully via admin MetaMask",
                "transactionHash": tx_hash
            }
        else:
            # Fallback to demo mode
            if batch_id in batches_storage:
                raise HTTPException(status_code=400, detail="Batch ID already exists")
            
            # Create batch with realistic transaction hash
            batch = {
                "batchId": batch_id,
                "productType": product_type,
                "created": datetime.now().isoformat() + "Z",
                "currentStage": "Created",
                "currentLocation": "Origin Farm",
                "locationHistory": [
                    {
                        "stage": "Created",
                        "location": "Origin Farm",
                        "timestamp": datetime.now().isoformat() + "Z",
                        "transactionHash": f"DEMO-{hash(batch_id + 'admin' + str(datetime.now().timestamp())) % 0xffffffffffffffff:016x}",
                        "updatedBy": "admin"
                    }
                ],
                "alerts": [],
                "isActive": True,
                "isFinalStage": False
            }
            
            batches_storage[batch_id] = batch
            
            return {
                "success": True,
                "message": "Batch created successfully via admin MetaMask (demo mode)",
                "transactionHash": f"DEMO-{hash(batch_id + 'admin' + str(datetime.now().timestamp())) % 0xffffffffffffffff:016x}"
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create batch: {str(e)}")

@app.post("/admin/metamask/update-stage")
async def admin_update_stage_with_metamask(request: dict):
    """Admin updates batch stage - backend handles MetaMask transaction internally"""
    batch_id = request.get("batchId")
    stage = request.get("stage")
    location = request.get("location")
    
    if not batch_id or not stage or not location:
        raise HTTPException(status_code=400, detail="All fields required")
    
    try:
        if blockchain_service:
            # Check if batch exists and get current state
            batch_data = await blockchain_service.get_batch_details(batch_id)
            if not batch_data:
                raise HTTPException(status_code=404, detail="Batch not found")
            
            if batch_data["isFinalStage"]:
                raise HTTPException(status_code=400, detail="Cannot update batch in final stage")
            
            # Update on blockchain using system wallet
            tx_hash = await blockchain_service.update_location(batch_id, stage, location, "admin")
            
            return {
                "success": True,
                "message": "Batch stage updated successfully via admin MetaMask",
                "transactionHash": tx_hash
            }
        else:
            # Fallback to demo mode
            if batch_id not in batches_storage:
                raise HTTPException(status_code=404, detail="Batch not found")
            
            batch = batches_storage[batch_id]
            
            if batch["isFinalStage"]:
                raise HTTPException(status_code=400, detail="Cannot update batch in final stage")
            
            # Update batch
            batch["currentStage"] = stage
            batch["currentLocation"] = location
            batch["isFinalStage"] = (stage == "Selling")
            
            # Add to history with admin transaction hash
            batch["locationHistory"].insert(0, {
                "stage": stage,
                "location": location,
                "timestamp": datetime.now().isoformat() + "Z",
                "transactionHash": f"DEMO-{hash(batch_id + stage + 'admin' + str(datetime.now().timestamp())) % 0xffffffffffffffff:016x}",
                "updatedBy": "admin"
            })
            
            return {
                "success": True,
                "message": "Batch stage updated successfully via admin MetaMask (demo mode)",
                "transactionHash": f"DEMO-{hash(batch_id + stage + 'admin' + str(datetime.now().timestamp())) % 0xffffffffffffffff:016x}"
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update batch: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(
        "main_simple:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )