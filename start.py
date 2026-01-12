#!/usr/bin/env python3
"""
Smart startup script for FreshChain Backend
Automatically starts in the best available mode
"""
import subprocess
import sys
import os

def check_full_dependencies():
    """Check if full blockchain dependencies are available"""
    try:
        import web3
        import eth_account
        from pydantic_settings import BaseSettings
        return True
    except ImportError:
        return False

def check_basic_dependencies():
    """Check if basic dependencies are available"""
    try:
        import fastapi
        import uvicorn
        return True
    except ImportError:
        return False

def install_basic_deps():
    """Install minimal dependencies for demo mode"""
    print("📦 Installing basic dependencies...")
    try:
        subprocess.run([
            sys.executable, "-m", "pip", "install", 
            "fastapi==0.103.2", 
            "uvicorn==0.23.2", 
            "python-dotenv==1.0.0"
        ], check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError:
        return False

def start_demo_mode():
    """Start in demo mode with mock data"""
    print("🚀 Starting FreshChain Backend in DEMO MODE")
    print("=" * 50)
    print("✅ Using mock blockchain data")
    print("✅ No wallet required")
    print("✅ All API endpoints available")
    print("✅ Demo users: admin/retailer/transporter/consumer")
    print("✅ Password: demo123")
    print("=" * 50)
    print("🌐 Server starting at: http://localhost:8000")
    print("📚 API docs: http://localhost:8000/docs")
    print("=" * 50)
    print("Press Ctrl+C to stop the server")
    print()
    
    try:
        # Import and run directly to avoid subprocess issues
        import uvicorn
        uvicorn.run("main_simple:app", host="0.0.0.0", port=8000, reload=True)
    except ImportError:
        # Fallback to subprocess if uvicorn not available
        subprocess.run([sys.executable, "main_simple.py"], check=True)
    except KeyboardInterrupt:
        print("\n👋 Server stopped by user")

def start_full_mode():
    """Start in full blockchain mode"""
    print("🚀 Starting FreshChain Backend in FULL MODE")
    print("=" * 50)
    
    if not os.path.exists('.env'):
        print("❌ .env file not found!")
        print("Please create .env file with your configuration")
        print("Falling back to demo mode...")
        print()
        start_demo_mode()
        return
    
    if not check_full_dependencies():
        print("❌ Full blockchain dependencies not installed!")
        print("Please run: pip install web3 eth-account pydantic-settings")
        print("Falling back to demo mode...")
        print()
        start_demo_mode()
        return
    
    try:
        import uvicorn
        uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
    except ImportError:
        subprocess.run([sys.executable, "run.py"], check=True)
    except KeyboardInterrupt:
        print("\n👋 Server stopped by user")

def main():
    print("🌱 FreshChain Backend")
    print("=" * 30)
    
    # Check if basic dependencies are available
    if not check_basic_dependencies():
        print("📦 Installing basic dependencies...")
        if not install_basic_deps():
            print("❌ Failed to install dependencies")
            print("Please run: pip install fastapi uvicorn python-dotenv")
            return False
    
    # Auto-detect the best mode
    if check_full_dependencies() and os.path.exists('.env'):
        print("🔍 Full blockchain setup detected")
        choice = input("Start in full mode? (y/N): ").strip().lower()
        if choice == 'y':
            start_full_mode()
            return
    
    print("🔍 Starting in demo mode (recommended)")
    start_demo_mode()

if __name__ == "__main__":
    main()