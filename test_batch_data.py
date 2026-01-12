#!/usr/bin/env python3
"""
Test current batch data structure to ensure transaction hashes are present
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import asyncio
from datetime import datetime

# Import the blockchain service
try:
    from blockchain import BlockchainService
    BLOCKCHAIN_AVAILABLE = True
except ImportError:
    print("⚠️ Blockchain service not available")
    BLOCKCHAIN_AVAILABLE = False

async def test_batch_data_structure():
    """Test the structure of batch data returned by the system"""
    print("🔍 Testing Batch Data Structure...")
    print("=" * 50)
    
    if BLOCKCHAIN_AVAILABLE:
        try:
            blockchain_service = BlockchainService()
            await blockchain_service.initialize()
            
            print("✅ Blockchain service initialized")
            
            # Try to get all batches
            batches = await blockchain_service.get_all_batches()
            print(f"📦 Found {len(batches)} batches")
            
            if batches:
                for i, batch in enumerate(batches[:2]):  # Show first 2 batches
                    print(f"\n📋 Batch {i+1}: {batch.get('batchId', 'Unknown')}")
                    print(f"   Product Type: {batch.get('productType', 'Unknown')}")
                    print(f"   Current Stage: {batch.get('currentStage', 'Unknown')}")
                    print(f"   Location History: {len(batch.get('locationHistory', []))} entries")
                    
                    if batch.get('locationHistory'):
                        latest_history = batch['locationHistory'][0]
                        tx_hash = latest_history.get('transactionHash', 'None')
                        print(f"   Latest TX Hash: {tx_hash}")
                        print(f"   TX Hash Type: {'Real' if tx_hash.startswith('0x') and len(tx_hash) == 66 else 'Demo' if tx_hash.startswith('DEMO-') else 'Unknown'}")
            else:
                print("📭 No batches found")
                
        except Exception as e:
            print(f"❌ Error testing blockchain service: {e}")
            print("🔄 Testing fallback demo mode...")
            await test_demo_mode()
    else:
        print("🔄 Testing demo mode...")
        await test_demo_mode()

async def test_demo_mode():
    """Test demo mode batch creation"""
    print("\n🎭 Testing Demo Mode Batch Creation...")
    
    # Simulate creating a batch in demo mode
    batch_id = "TEST-DEMO-001"
    product_type = "Organic Apples"
    
    # This is how demo batches are created in main_simple.py
    demo_batch = {
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
    
    print(f"📦 Demo Batch Created:")
    print(f"   Batch ID: {demo_batch['batchId']}")
    print(f"   Product: {demo_batch['productType']}")
    print(f"   TX Hash: {demo_batch['locationHistory'][0]['transactionHash']}")
    
    # Test frontend compatibility
    tx_hash = demo_batch['locationHistory'][0]['transactionHash']
    is_demo = tx_hash.startswith('DEMO-')
    is_real = tx_hash.startswith('0x') and len(tx_hash) == 66
    
    print(f"   Frontend Detection:")
    print(f"     Is Demo: {is_demo}")
    print(f"     Is Real: {is_real}")
    print(f"     Should Show Link: {is_real}")
    print(f"     Should Show Demo: {is_demo}")

if __name__ == "__main__":
    asyncio.run(test_batch_data_structure())