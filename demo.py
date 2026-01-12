#!/usr/bin/env python3
"""
Demo script to test FreshChain Backend API
Run this after starting the backend server
"""
import asyncio
import aiohttp
import json

BACKEND_URL = "http://localhost:8000"

async def test_backend():
    async with aiohttp.ClientSession() as session:
        print("🧪 Testing FreshChain Backend API\n")
        
        # Test health endpoint
        print("1. Testing health endpoint...")
        try:
            async with session.get(f"{BACKEND_URL}/health") as response:
                data = await response.json()
                print(f"   ✅ Health: {data}")
        except Exception as e:
            print(f"   ❌ Health check failed: {e}")
        
        # Test create batch
        print("\n2. Testing batch creation...")
        batch_data = {
            "batchId": "DEMO-001",
            "productType": "Organic Apples"
        }
        try:
            async with session.post(
                f"{BACKEND_URL}/batch/create",
                json=batch_data,
                headers={"Content-Type": "application/json"}
            ) as response:
                data = await response.json()
                print(f"   ✅ Create batch: {data}")
        except Exception as e:
            print(f"   ❌ Create batch failed: {e}")
        
        # Test update stage
        print("\n3. Testing stage update...")
        update_data = {
            "batchId": "DEMO-001",
            "status": "In Transit",
            "location": "Distribution Center"
        }
        try:
            async with session.post(
                f"{BACKEND_URL}/batch/update-stage",
                json=update_data,
                headers={"Content-Type": "application/json"}
            ) as response:
                data = await response.json()
                print(f"   ✅ Update stage: {data}")
        except Exception as e:
            print(f"   ❌ Update stage failed: {e}")
        
        # Test get batch details
        print("\n4. Testing batch retrieval...")
        try:
            async with session.get(f"{BACKEND_URL}/batch/DEMO-001") as response:
                data = await response.json()
                print(f"   ✅ Get batch: {data}")
        except Exception as e:
            print(f"   ❌ Get batch failed: {e}")
        
        print("\n🎉 Demo completed!")

if __name__ == "__main__":
    print("Make sure the backend server is running on http://localhost:8000")
    print("Start it with: python run.py\n")
    asyncio.run(test_backend())