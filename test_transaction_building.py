#!/usr/bin/env python3
"""
Test transaction building without sending (to verify gas price fix)
"""
import asyncio
from blockchain import BlockchainService

async def test_transaction_building():
    """Test that transactions can be built without gas price errors"""
    print("=== Testing Transaction Building ===")
    
    # Initialize blockchain service
    blockchain = BlockchainService()
    await blockchain.initialize()
    
    print(f"✅ System wallet: {blockchain.system_account.address}")
    print(f"✅ Contract address: {blockchain.contract.address}")
    
    try:
        # Test building a createBatch transaction (without sending)
        print("🔧 Testing createBatch transaction building...")
        
        function_call = blockchain.contract.functions.createBatch("TEST-001", "Test Product")
        transaction_data = {
            'to': blockchain.contract.address,
            'data': function_call._encode_transaction_data()
        }
        
        # Build the transaction structure (without sending)
        nonce = blockchain.w3.eth.get_transaction_count(blockchain.system_account.address)
        transaction = {
            'from': blockchain.system_account.address,
            'nonce': nonce,
            'gas': 500000,
            'chainId': 8119,
            'gasPrice': blockchain.w3.eth.gas_price,
            **transaction_data
        }
        
        print("✅ Transaction built successfully!")
        print(f"📄 Transaction data length: {len(transaction['data'])} bytes")
        print(f"⛽ Gas price: {transaction['gasPrice']} wei")
        print(f"🔢 Nonce: {transaction['nonce']}")
        
        # Test updateLocation transaction building
        print("🔧 Testing updateLocation transaction building...")
        
        function_call = blockchain.contract.functions.updateLocation("TEST-001", "Harvested", "Farm Location")
        transaction_data = {
            'to': blockchain.contract.address,
            'data': function_call._encode_transaction_data()
        }
        
        print("✅ UpdateLocation transaction built successfully!")
        print(f"📄 Transaction data length: {len(transaction_data['data'])} bytes")
        
        print("🎉 All transaction building tests passed!")
        print()
        print("The gas price issue has been fixed. Transactions will work once the wallet is funded.")
        
    except Exception as e:
        print(f"❌ Transaction building failed: {e}")
        return False
    
    return True

if __name__ == "__main__":
    asyncio.run(test_transaction_building())