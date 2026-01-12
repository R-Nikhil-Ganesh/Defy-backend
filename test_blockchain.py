#!/usr/bin/env python3
"""
Test blockchain connection and contract interaction
"""
import asyncio
from blockchain import BlockchainService

async def test_blockchain():
    """Test blockchain connection and basic operations"""
    print("=== Testing Blockchain Connection ===")
    
    # Initialize blockchain service
    blockchain = BlockchainService()
    await blockchain.initialize()
    
    print(f"✅ Connected to: {blockchain.w3.client_version}")
    print(f"✅ System wallet: {blockchain.system_account.address}")
    print(f"✅ Contract address: {blockchain.contract.address}")
    
    # Check wallet balance
    balance_wei = blockchain.w3.eth.get_balance(blockchain.system_account.address)
    balance_shm = blockchain.w3.from_wei(balance_wei, 'ether')
    print(f"💰 Wallet balance: {balance_shm} SHM")
    
    if balance_shm == 0:
        print("⚠️  Wallet has no SHM tokens!")
        print("🔗 Fund your wallet at: https://faucet.shardeum.org/")
        print(f"📍 Address to fund: {blockchain.system_account.address}")
        return
    
    # Test contract connection
    try:
        # Try to call a read-only function
        print("🔍 Testing contract connection...")
        
        # Test getting batch details for a non-existent batch
        batch_data = await blockchain.get_batch_details("TEST-BATCH-001")
        if batch_data is None:
            print("✅ Contract connection working (batch not found as expected)")
        else:
            print(f"📦 Found existing batch: {batch_data}")
            
    except Exception as e:
        print(f"❌ Contract interaction failed: {e}")
        return
    
    print("🎉 Blockchain connection test completed successfully!")
    print()
    print("Next steps:")
    print("1. Fund the wallet with SHM tokens if balance is 0")
    print("2. Test creating a batch through the API")
    print("3. Verify transactions on Shardeum explorer")

if __name__ == "__main__":
    asyncio.run(test_blockchain())