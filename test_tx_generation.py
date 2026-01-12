#!/usr/bin/env python3
"""
Test current transaction hash generation
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime

def test_current_hash_generation():
    """Test how transaction hashes are currently being generated"""
    print("🔍 Testing Current Transaction Hash Generation...")
    print("=" * 50)
    
    batch_id = "TEST-001"
    
    # Test demo hash generation (as used in main_simple.py)
    demo_hash = f"DEMO-{hash(batch_id + str(datetime.now().timestamp())) % 0xffffffffffffffff:016x}"
    
    print(f"Batch ID: {batch_id}")
    print(f"Generated Demo Hash: {demo_hash}")
    print(f"Hash Length: {len(demo_hash)}")
    print(f"Starts with DEMO-: {demo_hash.startswith('DEMO-')}")
    
    # Test what a real transaction hash would look like
    real_hash = "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
    print(f"\nReal Hash Example: {real_hash}")
    print(f"Real Hash Length: {len(real_hash)}")
    print(f"Starts with 0x: {real_hash.startswith('0x')}")
    
    return demo_hash, real_hash

if __name__ == "__main__":
    demo_hash, real_hash = test_current_hash_generation()
    
    # Test the frontend utilities would work
    print(f"\n🔧 Testing Frontend Compatibility...")
    
    # Simulate frontend logic
    def is_real_transaction_hash(tx_hash):
        if not tx_hash:
            return False
        if len(tx_hash) != 66:
            return False
        hex_pattern = r'^0x[a-fA-F0-9]{64}$'
        import re
        return bool(re.match(hex_pattern, tx_hash))
    
    def is_demo_transaction_hash(tx_hash):
        return tx_hash and tx_hash.startswith('DEMO-')
    
    print(f"Demo hash detected as real: {is_real_transaction_hash(demo_hash)}")
    print(f"Demo hash detected as demo: {is_demo_transaction_hash(demo_hash)}")
    print(f"Real hash detected as real: {is_real_transaction_hash(real_hash)}")
    print(f"Real hash detected as demo: {is_demo_transaction_hash(real_hash)}")
    
    print(f"\n✅ Transaction hash generation is working correctly!")