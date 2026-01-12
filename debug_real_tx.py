#!/usr/bin/env python3
"""
Debug script to check what actual transaction hashes are being returned from blockchain
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import asyncio
import json

async def debug_blockchain_transactions():
    """Debug what transaction hashes are actually being returned"""
    print("🔍 Debugging Real Blockchain Transaction Hashes...")
    print("=" * 60)
    
    try:
        from blockchain import BlockchainService
        
        blockchain_service = BlockchainService()
        await blockchain_service.initialize()
        
        print("✅ Blockchain service initialized")
        print(f"📡 Connected to: {blockchain_service.w3.provider.endpoint_uri}")
        print(f"🏦 System wallet: {blockchain_service.system_account.address}")
        
        # Get all batches
        batches = await blockchain_service.get_all_batches()
        print(f"📦 Found {len(batches)} batches from blockchain")
        
        for i, batch in enumerate(batches):
            print(f"\n📋 Batch {i+1}: {batch['batchId']}")
            print(f"   Product: {batch['productType']}")
            print(f"   Stage: {batch['currentStage']}")
            print(f"   Location History: {len(batch.get('locationHistory', []))} entries")
            
            if batch.get('locationHistory'):
                for j, history in enumerate(batch['locationHistory'][:3]):  # Show first 3 history entries
                    tx_hash = history.get('transactionHash', 'None')
                    print(f"   History {j+1}:")
                    print(f"     Stage: {history.get('stage', 'Unknown')}")
                    print(f"     TX Hash: {tx_hash}")
                    print(f"     TX Length: {len(tx_hash) if tx_hash else 0}")
                    print(f"     Starts with 0x: {tx_hash.startswith('0x') if tx_hash else False}")
                    print(f"     Is 66 chars: {len(tx_hash) == 66 if tx_hash else False}")
                    print(f"     Is Real Format: {tx_hash.startswith('0x') and len(tx_hash) == 66 if tx_hash else False}")
                    print(f"     Is Demo Format: {tx_hash.startswith('DEMO-') if tx_hash else False}")
                    
                    # Check if it's a valid hex string
                    if tx_hash and tx_hash.startswith('0x') and len(tx_hash) == 66:
                        try:
                            int(tx_hash, 16)  # Try to parse as hex
                            print(f"     ✅ Valid hex format")
                        except ValueError:
                            print(f"     ❌ Invalid hex format")
                    
        # Also check if we can get a specific batch
        if batches:
            first_batch = batches[0]
            print(f"\n🔍 Detailed check of first batch: {first_batch['batchId']}")
            
            # Get batch details directly
            batch_details = await blockchain_service.get_batch_details(first_batch['batchId'])
            if batch_details:
                print(f"   Direct batch query result:")
                print(f"   Location History: {len(batch_details.get('locationHistory', []))}")
                if batch_details.get('locationHistory'):
                    latest = batch_details['locationHistory'][0]
                    print(f"   Latest TX: {latest.get('transactionHash', 'None')}")
                    
                    # Check the raw blockchain data
                    print(f"\n🔧 Raw blockchain contract call...")
                    try:
                        raw_batch_data = blockchain_service.contract.functions.getBatchDetails(first_batch['batchId']).call()
                        print(f"   Raw contract response: {raw_batch_data}")
                        
                        if len(raw_batch_data) >= 3:
                            batch_id, product_type, history = raw_batch_data[0], raw_batch_data[1], raw_batch_data[2]
                            print(f"   History from contract: {len(history)} entries")
                            if history:
                                print(f"   First history entry: {history[0]}")
                    except Exception as e:
                        print(f"   ❌ Error calling contract: {e}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_blockchain_transactions())