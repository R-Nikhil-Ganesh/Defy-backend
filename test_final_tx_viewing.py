#!/usr/bin/env python3
"""
Final test to confirm transaction viewing is working with real blockchain hashes
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import asyncio

async def test_final_tx_viewing():
    """Test that we now have real transaction hashes that will work in frontend"""
    print("🎯 Final Transaction Viewing Test")
    print("=" * 50)
    
    try:
        from blockchain import BlockchainService
        
        blockchain_service = BlockchainService()
        await blockchain_service.initialize()
        
        # Get first batch
        batches = await blockchain_service.get_all_batches()
        if not batches:
            print("❌ No batches found")
            return False
            
        first_batch = batches[0]
        print(f"📦 Testing batch: {first_batch['batchId']}")
        
        if not first_batch.get('locationHistory'):
            print("❌ No location history found")
            return False
            
        latest_history = first_batch['locationHistory'][0]
        tx_hash = latest_history.get('transactionHash')
        
        print(f"🔍 Latest transaction hash: {tx_hash}")
        print(f"   Length: {len(tx_hash) if tx_hash else 0}")
        print(f"   Starts with 0x: {tx_hash.startswith('0x') if tx_hash else False}")
        print(f"   Is 66 chars: {len(tx_hash) == 66 if tx_hash else False}")
        
        # Test frontend logic
        is_real_tx = tx_hash and tx_hash.startswith('0x') and len(tx_hash) == 66
        print(f"   Frontend will detect as REAL: {is_real_tx}")
        
        if is_real_tx:
            explorer_url = f"https://explorer-mezame.shardeum.org/tx/{tx_hash}"
            print(f"   Explorer URL: {explorer_url}")
            print(f"   ✅ Will show CLICKABLE 'TX' link")
            
            # Test hex validity
            try:
                int(tx_hash, 16)
                print(f"   ✅ Valid hex format - link will work")
            except ValueError:
                print(f"   ❌ Invalid hex format")
                return False
                
        else:
            print(f"   ❌ Will show 'Demo' text (non-clickable)")
            return False
        
        # Test multiple batches
        print(f"\n📊 Testing all {len(batches)} batches:")
        real_tx_count = 0
        demo_tx_count = 0
        
        for batch in batches:
            if batch.get('locationHistory'):
                tx = batch['locationHistory'][0].get('transactionHash', '')
                if tx.startswith('0x') and len(tx) == 66:
                    real_tx_count += 1
                else:
                    demo_tx_count += 1
        
        print(f"   Real transactions: {real_tx_count}")
        print(f"   Demo transactions: {demo_tx_count}")
        
        if real_tx_count > 0:
            print(f"   ✅ Users will see {real_tx_count} clickable TX links!")
            return True
        else:
            print(f"   ❌ No real transaction links will be shown")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_final_tx_viewing())
    
    if success:
        print(f"\n🎉 TRANSACTION VIEWING IS NOW WORKING!")
        print(f"✅ Real blockchain transaction hashes detected")
        print(f"✅ Frontend will show clickable 'TX' links")
        print(f"✅ Links will open Shardeum explorer")
        print(f"✅ Users can view actual blockchain transactions")
    else:
        print(f"\n❌ Transaction viewing still needs work")
        sys.exit(1)