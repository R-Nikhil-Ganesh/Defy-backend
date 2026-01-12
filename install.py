#!/usr/bin/env python3
"""
Installation script for FreshChain Backend
Handles dependency installation with fallbacks for common issues
"""
import subprocess
import sys
import os

def run_command(command, description):
    """Run a command and handle errors gracefully"""
    print(f"\n🔄 {description}...")
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print(f"✅ {description} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed:")
        print(f"Error: {e.stderr}")
        return False

def install_dependencies():
    """Install dependencies with fallback options"""
    print("🚀 Installing FreshChain Backend Dependencies")
    
    # Try to install with current requirements
    if run_command("pip install -r requirements.txt", "Installing dependencies"):
        return True
    
    print("\n⚠️  Standard installation failed. Trying alternative approach...")
    
    # Fallback: Install dependencies one by one
    dependencies = [
        "fastapi==0.103.2",
        "uvicorn[standard]==0.23.2", 
        "pydantic==2.4.2",
        "pydantic-settings==2.0.3",
        "web3==6.10.0",
        "eth-account==0.8.0",
        "python-multipart==0.0.6",
        "python-dotenv==1.0.0",
        "requests==2.31.0"
    ]
    
    failed_packages = []
    
    for package in dependencies:
        if not run_command(f"pip install {package}", f"Installing {package}"):
            failed_packages.append(package)
    
    if failed_packages:
        print(f"\n❌ Failed to install: {', '.join(failed_packages)}")
        print("\n🔧 Try these solutions:")
        print("1. Update pip: python -m pip install --upgrade pip")
        print("2. Install Visual Studio Build Tools (for Windows)")
        print("3. Use conda instead: conda install -c conda-forge <package>")
        return False
    
    return True

def setup_environment():
    """Set up environment file"""
    if not os.path.exists('.env'):
        if os.path.exists('.env.example'):
            run_command("copy .env.example .env", "Creating environment file")
            print("\n📝 Please edit .env file with your configuration:")
            print("   - SYSTEM_PRIVATE_KEY: Your wallet private key")
            print("   - CONTRACT_ADDRESS: Your deployed contract address")
        else:
            print("⚠️  .env.example not found. Please create .env manually.")
    else:
        print("✅ .env file already exists")

def main():
    print("=" * 60)
    print("🌱 FreshChain Backend Installation")
    print("=" * 60)
    
    # Check Python version
    if sys.version_info < (3, 8):
        print("❌ Python 3.8+ required. Current version:", sys.version)
        return False
    
    print(f"✅ Python version: {sys.version}")
    
    # Install dependencies
    if not install_dependencies():
        return False
    
    # Setup environment
    setup_environment()
    
    print("\n" + "=" * 60)
    print("🎉 Installation completed!")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Edit .env file with your configuration")
    print("2. Run: python run.py")
    print("3. Visit: http://localhost:8000/docs")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)