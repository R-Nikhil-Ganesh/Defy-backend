#!/usr/bin/env python3
"""
Test script to verify transaction viewing functionality
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils import is_valid_transaction_hash, generate_explorer_url, is_real_transaction_hash
from config import settings

def test_transaction_utilities():
    """Test transaction utility functions"""
    print("🔍 Testing Transaction Viewing Utilities...")
    print("=" * 60)
    
    # Test cases
    test_cases = [
        {
            "name": "Real Transaction Hash",
            "hash": "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
            "expected_valid": True,
            "expected_real": True,
            "should_have_url": True
        },
        {
            "name": "Demo Transaction Hash",
            "hash": "DEMO-1234567890abcdef",
            "expected_valid": False,
            "expected_real": False,
            "should_have_url": False
        },
        {
            "name": "Invalid Hash (too short)",
            "hash": "0x123456",
            "expected_valid": False,
            "expected_real": False,
            "should_have_url": False
        },
        {
            "name": "Empty Hash",
            "hash": "",
            "expected_valid": False,
            "expected_real": False,
            "should_have_url": False
        }
    ]
    
    all_passed = True
    
    for test_case in test_cases:
        print(f"\n📝 Testing: {test_case['name']}")
        print(f"   Hash: {test_case['hash']}")
        
        # Test validation
        is_valid = is_valid_transaction_hash(test_case['hash'])
        is_real = is_real_transaction_hash(test_case['hash'])
        explorer_url = generate_explorer_url(test_case['hash'])
        
        print(f"   Valid: {is_valid} (expected: {test_case['expected_valid']})")
        print(f"   Real: {is_real} (expected: {test_case['expected_real']})")
        print(f"   Explorer URL: {explorer_url}")
        
        # Check results
        if is_valid != test_case['expected_valid']:
            print(f"   ❌ FAIL: Validation mismatch")
            all_passed = False
        elif is_real != test_case['expected_real']:
            print(f"   ❌ FAIL: Real check mismatch")
            all_passed = False
        elif test_case['should_have_url'] and not explorer_url:
            print(f"   ❌ FAIL: Should have explorer URL")
            all_passed = False
        elif not test_case['should_have_url'] and explorer_url:
            print(f"   ❌ FAIL: Should not have explorer URL")
            all_passed = False
        else:
            print(f"   ✅ PASS")
    
    print(f"\n🌐 Explorer Configuration:")
    print(f"   Base URL: {settings.EXPLORER_BASE_URL}")
    print(f"   TX URL: {settings.EXPLORER_TX_URL}")
    
    if all_passed:
        print(f"\n🎉 All transaction utility tests PASSED!")
        return True
    else:
        print(f"\n❌ Some transaction utility tests FAILED!")
        return False

def test_demo_vs_real_hashes():
    """Test distinguishing between demo and real hashes"""
    print(f"\n🔄 Testing Demo vs Real Hash Detection...")
    print("=" * 60)
    
    # Generate some demo hashes like the system does
    import datetime
    batch_id = "TEST-001"
    demo_hash = f"DEMO-{hash(batch_id + str(datetime.datetime.now().timestamp())) % 0xffffffffffffffff:016x}"
    real_hash = "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
    
    print(f"Demo hash: {demo_hash}")
    print(f"Real hash: {real_hash}")
    
    demo_is_real = is_real_transaction_hash(demo_hash)
    real_is_real = is_real_transaction_hash(real_hash)
    
    print(f"Demo hash detected as real: {demo_is_real} (should be False)")
    print(f"Real hash detected as real: {real_is_real} (should be True)")
    
    if not demo_is_real and real_is_real:
        print("✅ Demo vs Real detection working correctly!")
        return True
    else:
        print("❌ Demo vs Real detection failed!")
        return False

if __name__ == "__main__":
    try:
        test1_passed = test_transaction_utilities()
        test2_passed = test_demo_vs_real_hashes()
        
        if test1_passed and test2_passed:
            print(f"\n🎉 ALL TRANSACTION VIEWING TESTS PASSED!")
            print(f"✅ Transaction links will now work properly")
            print(f"✅ Demo transactions will be clearly marked")
            print(f"✅ Real transactions will link to Shardeum explorer")
        else:
            print(f"\n❌ SOME TESTS FAILED!")
            sys.exit(1)
            
    except Exception as e:
        print(f"❌ Transaction viewing test FAILED: {e}")
        sys.exit(1)