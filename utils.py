#!/usr/bin/env python3
"""
Utility functions for FreshChain backend
"""
import re
from typing import Optional
from config import settings

def is_valid_transaction_hash(tx_hash: str) -> bool:
    """
    Validate if a transaction hash is a valid Ethereum/Shardeum transaction hash
    """
    if not tx_hash:
        return False
    
    # Check if it's a valid hex string starting with 0x and 64 characters long
    pattern = r'^0x[a-fA-F0-9]{64}$'
    return bool(re.match(pattern, tx_hash))

def generate_explorer_url(tx_hash: str) -> Optional[str]:
    """
    Generate explorer URL for a transaction hash
    Returns None if the transaction hash is invalid
    """
    if not is_valid_transaction_hash(tx_hash):
        return None
    
    return f"{settings.EXPLORER_TX_URL}/{tx_hash}"

def is_real_transaction_hash(tx_hash: str) -> bool:
    """
    Determine if a transaction hash is real (from blockchain) or generated (demo mode)
    Real transaction hashes are 66 characters long (0x + 64 hex chars)
    Generated hashes are shorter and use Python's hash function
    """
    if not tx_hash:
        return False
    
    # Real transaction hashes are always 66 characters (0x + 64 hex)
    if len(tx_hash) != 66:
        return False
    
    # Check if it follows the proper hex format
    return is_valid_transaction_hash(tx_hash)

def format_transaction_hash_display(tx_hash: str) -> str:
    """
    Format transaction hash for display
    """
    if not tx_hash:
        return "N/A"
    
    if is_real_transaction_hash(tx_hash):
        # Show first 6 and last 4 characters for real hashes
        return f"{tx_hash[:6]}...{tx_hash[-4:]}"
    else:
        # Show as demo for generated hashes
        return f"Demo: {tx_hash[:8]}..."