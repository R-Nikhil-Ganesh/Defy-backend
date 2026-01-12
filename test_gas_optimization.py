#!/usr/bin/env python3
"""
Test script to verify gas optimization settings
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import settings

def test_gas_optimization():
    """Test that gas optimization settings are properly configured"""
    print("🔧 Testing Gas Optimization Settings...")
    print("=" * 50)
    
    # Test gas limit reduction
    assert settings.GAS_LIMIT == 150000, f"Expected 150000, got {settings.GAS_LIMIT}"
    print(f"✅ Gas Limit: {settings.GAS_LIMIT:,} (70% reduction from 500,000)")
    
    # Test gas price optimization
    assert settings.GAS_PRICE_GWEI == 1, f"Expected 1, got {settings.GAS_PRICE_GWEI}"
    print(f"✅ Gas Price: {settings.GAS_PRICE_GWEI} gwei (ultra-low for Shardeum)")
    
    # Test gas estimation buffer
    assert settings.GAS_ESTIMATION_BUFFER == 1.15, f"Expected 1.15, got {settings.GAS_ESTIMATION_BUFFER}"
    print(f"✅ Gas Buffer: {settings.GAS_ESTIMATION_BUFFER}x (reduced from 1.2x)")
    
    # Calculate cost savings
    old_max_cost = 500000 * 1 / 1e9  # Old settings
    new_max_cost = settings.GAS_LIMIT * settings.GAS_PRICE_GWEI / 1e9
    savings_percent = ((old_max_cost - new_max_cost) / old_max_cost) * 100
    
    print("\n💰 Cost Analysis:")
    print(f"   Old max cost per transaction: {old_max_cost:.6f} SHM")
    print(f"   New max cost per transaction: {new_max_cost:.6f} SHM")
    print(f"   💚 Cost savings: {savings_percent:.1f}%")
    
    # Estimate costs for batch operations
    print(f"\n📊 Estimated Costs (with current 14,000+ SHM balance):")
    transactions_possible = 14000 / new_max_cost
    print(f"   Transactions possible: {transactions_possible:,.0f}")
    print(f"   Cost per batch creation: ~{new_max_cost:.6f} SHM")
    print(f"   Cost per stage update: ~{new_max_cost:.6f} SHM")
    
    print("\n🎉 Gas optimization test PASSED!")
    return True

if __name__ == "__main__":
    try:
        test_gas_optimization()
    except Exception as e:
        print(f"❌ Gas optimization test FAILED: {e}")
        sys.exit(1)