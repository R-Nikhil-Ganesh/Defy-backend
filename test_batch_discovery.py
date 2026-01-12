#!/usr/bin/env python3
"""
Test script to discover all batches on the blockchain
"""
import asyncio
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from blockchain import BlockchainService
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_batch_discovery():
    """Test batch discovery methods"""
    try:
        # Initialize blockchain service
        blockchain_service = BlockchainService()
        await blockchain_service.initialize()
        
        print("=" * 60)
        print("BLOCKCHAIN BATCH DISCOVERY TEST")
        print("=" * 60)
        
        # Test 1: Get all batches
        print("\n1. Getting all batches...")
        batches = await blockchain_service.get_all_batches()
        
        print(f"\nFound {len(batches)} batches:")
        for i, batch in enumerate(batches, 1):
            print(f"  {i}. {batch['batchId']} - {batch['productType']} - {batch['currentStage']}")
        
        # Test 2: Try specific batch IDs that might exist
        print("\n2. Testing specific batch IDs...")
        test_ids = [
            "Demo-001", "TEST-001", "BATCH-001", "APPLE-001", 
            "TOMATO-001", "LETTUCE-001", "ORGANIC-001"
        ]
        
        for batch_id in test_ids:
            try:
                batch_details = await blockchain_service.get_batch_details(batch_id)
                if batch_details:
                    print(f"  ✓ Found: {batch_id} - {batch_details['productType']}")
                else:
                    print(f"  ✗ Not found: {batch_id}")
            except Exception as e:
                print(f"  ✗ Error checking {batch_id}: {e}")
        
        # Test 3: Check blockchain connection
        print("\n3. Checking blockchain connection...")
        is_connected = await blockchain_service.check_connection()
        print(f"  Blockchain connected: {is_connected}")
        
        if blockchain_service.w3:
            current_block = blockchain_service.w3.eth.block_number
            print(f"  Current block: {current_block}")
            print(f"  Contract address: {blockchain_service.contract.address}")
        
        print("\n" + "=" * 60)
        print("TEST COMPLETE")
        print("=" * 60)
        
    except Exception as e:
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_batch_discovery())