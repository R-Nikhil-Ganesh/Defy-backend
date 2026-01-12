#!/usr/bin/env python3
"""
Direct demo server startup - no prompts, just runs
"""
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def install_and_run():
    """Install dependencies and run server"""
    try:
        import fastapi
        import uvicorn
    except ImportError:
        print("📦 Installing required packages...")
        import subprocess
        subprocess.run([
            sys.executable, "-m", "pip", "install", 
            "fastapi==0.103.2", 
            "uvicorn==0.23.2", 
            "python-dotenv==1.0.0"
        ], check=True)
        print("✅ Packages installed!")

    print("🚀 FreshChain Backend Demo Server")
    print("=" * 40)
    print("✅ Demo mode with mock data")
    print("✅ All API endpoints working")
    print("✅ Users: admin/retailer/transporter/consumer")
    print("✅ Password: demo123")
    print("=" * 40)
    print("🌐 Server: http://localhost:8000")
    print("📚 API Docs: http://localhost:8000/docs")
    print("=" * 40)
    print("Press Ctrl+C to stop")
    print()

    try:
        import uvicorn
        uvicorn.run("main_simple:app", host="0.0.0.0", port=8000, reload=True)
    except KeyboardInterrupt:
        print("\n👋 Server stopped")

if __name__ == "__main__":
    install_and_run()