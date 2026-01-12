#!/usr/bin/env python3
"""
Generate a test wallet for FreshChain backend
"""
from eth_account import Account
import secrets

def generate_test_wallet():
    """Generate a new test wallet"""
    # Generate a random private key
    private_key = "0x" + secrets.token_hex(32)
    
    # Create account from private key
    account = Account.from_key(private_key)
    
    print("=== FreshChain Test Wallet Generated ===")
    print(f"Address: {account.address}")
    print(f"Private Key: {private_key}")
    print()
    print("IMPORTANT:")
    print("1. This is a TEST wallet - DO NOT use in production")
    print("2. You need to fund this wallet with SHM tokens from Shardeum faucet")
    print("3. Update the .env file with this private key")
    print()
    print("Shardeum Faucet: https://faucet.shardeum.org/")
    print(f"Fund this address: {account.address}")
    print()
    print("Update your .env file:")
    print(f"SYSTEM_PRIVATE_KEY={private_key}")
    
    return account.address, private_key

if __name__ == "__main__":
    generate_test_wallet()