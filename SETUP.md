# FreshChain Backend Setup Guide

## Quick Start (Demo Mode)

For immediate testing without blockchain setup:

```bash
cd "Backend FreshChain"
python start.py
```

Choose option 1 (Demo Mode) and the server will start with mock data at `http://localhost:8000`

## Full Setup (Blockchain Mode)

### Prerequisites

1. **Python 3.8+** installed
2. **Shardeum wallet** with testnet SHM tokens (for full mode)
3. **Deployed FreshChain smart contract** on Shardeum testnet (for full mode)

### Installation Options

#### Option 1: Automated Installation
```bash
cd "Backend FreshChain"
python install.py
```

#### Option 2: Manual Installation
```bash
cd "Backend FreshChain"
pip install -r requirements.txt
```

If you encounter dependency issues (especially on Windows), try:
```bash
pip install -r requirements-simple.txt
python start.py  # Choose demo mode
```

### Environment Configuration

1. **Copy the environment template:**
   ```bash
   cp .env.example .env
   ```

2. **Edit `.env` with your configuration:**
   ```env
   # System wallet private key (KEEP SECURE!)
   SYSTEM_PRIVATE_KEY=your_private_key_here
   
   # Your deployed contract address
   CONTRACT_ADDRESS=0x064e8D53bFF8023b0531FE845195c3741790870E
   
   # Shardeum RPC (default should work)
   SHARDEUM_RPC_URL=https://dapps.shardeum.org/
   CHAIN_ID=8081
   
   # API Configuration
   API_HOST=0.0.0.0
   API_PORT=8000
   DEBUG=true
   ```

3. **Update Contract ABI**
   
   Edit `contracts/FreshChain.json` with your contract's ABI:
   ```json
   {
     "abi": [
       // Your contract ABI here
     ]
   }
   ```

### Running the Backend

#### Smart Startup (Recommended)
```bash
python start.py
```
- Automatically detects if you have full setup
- Falls back to demo mode if needed
- Installs missing dependencies

#### Manual Startup
```bash
# Demo mode (no blockchain required)
python main_simple.py

# Full blockchain mode
python run.py
```

### Testing

1. **Health Check**: Visit `http://localhost:8000/health`
2. **API Docs**: Visit `http://localhost:8000/docs`
3. **Demo Test**: `python demo.py` (if in full mode)

## API Endpoints

### Authentication
- `POST /auth/login` - Login for all user types
- `GET /auth/me` - Get current user info

### Batch Management (Role-Protected)
- `POST /batch/create` - Create new batch (Admin/Retailer only)
- `POST /batch/update-stage` - Update batch stage (Retailer/Transporter only)
- `POST /batch/report-alert` - Report alerts (Retailer/Transporter only)

### Consumer Audit (Public)
- `GET /batch/{batchId}` - Get batch details (for QR scanning)

### System
- `GET /health` - Health check and blockchain status
- `GET /docs` - API documentation (Swagger UI)

## User Roles & Permissions

### Admin
- **Access**: All operations
- **MetaMask**: Not required (backend handles everything)
- **Permissions**: Create batches, update any stage, view all data

### Retailer
- **Access**: Create batches, update retail stages
- **MetaMask**: Not required
- **Permissions**: Create batches, update to "At Retailer"/"Selling" stages

### Transporter
- **Access**: Update transport stages
- **MetaMask**: Not required
- **Permissions**: Update to "In Transit"/"At Retailer" stages

### Consumer
- **Access**: Read-only QR scanning
- **MetaMask**: Not required
- **Permissions**: View batch details only

## Demo Users

All demo users use password: `demo123`

- **Username**: `admin` - Full system access
- **Username**: `retailer` - Batch creation and retail management
- **Username**: `transporter` - Transport stage updates
- **Username**: `consumer` - QR scanning only

## Demo Batches (Available in both modes)

- `APPLE-001` - Organic Apples (At Retailer)
- `TOMATO-002` - Cherry Tomatoes (In Transit)
- `LETTUCE-003` - Organic Lettuce (Selling - Final Stage)

## Batch Stages

The system enforces progressive stage updates:

1. **Created** - Initial batch creation
2. **Harvested** - Product harvested
3. **In Transit** - Being transported
4. **At Retailer** - Arrived at retail location
5. **Selling** - Final stage (locks further updates)

## Frontend Integration

The frontend is completely blockchain-free and only needs:

```env
# Frontend .env.local
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
```

## Troubleshooting

### Dependency Installation Issues

If you get Rust compilation errors:
```bash
# Use simplified requirements
pip install -r requirements-simple.txt
python start.py  # Choose demo mode
```

### Common Issues

#### "Failed to initialize blockchain service"
- Check private key format (should start with 0x)
- Ensure wallet has SHM tokens for gas
- Verify RPC URL is accessible
- **Solution**: Use demo mode first: `python start.py`

#### "Contract not found"
- Verify contract address is correct
- Check contract is deployed on Shardeum testnet
- Ensure ABI file is properly formatted
- **Solution**: Use demo mode for testing

#### "Transaction failed"
- Check wallet has sufficient SHM for gas
- Verify contract functions match the ABI
- Check gas limit settings in config.py
- **Solution**: Demo mode works without real transactions

### Windows-Specific Issues

If you encounter build tool errors:
1. Install Visual Studio Build Tools
2. Or use demo mode: `python start.py` → option 1
3. Or use WSL (Windows Subsystem for Linux)

## Production Deployment

For production:

1. Use environment variables for all sensitive data
2. Set up proper logging and monitoring
3. Configure CORS for your frontend domain
4. Use reverse proxy (nginx) for SSL termination
5. Consider hardware wallet or key management service
6. Set up database for caching and analytics (optional)

## File Structure

```
Backend FreshChain/
├── main.py              # Full FastAPI application
├── main_simple.py       # Demo mode with mock data
├── start.py             # Smart startup script
├── install.py           # Automated installation
├── auth.py              # Role-based authentication
├── blockchain.py        # Web3 integration
├── schemas.py           # Pydantic models
├── config.py            # Configuration
├── config_simple.py     # Simplified config
├── contracts/           # Smart contract ABI
│   └── FreshChain.json
├── requirements.txt     # Full dependencies
├── requirements-simple.txt # Minimal dependencies
├── run.py              # Full mode startup
├── demo.py             # Demo/testing script
├── .env.example        # Environment template
└── SETUP.md            # This file
```

## Key Features

✅ **Demo Mode**: Test without blockchain setup
✅ **Complete Blockchain Abstraction**: Frontend never touches Web3
✅ **Role-Based Security**: Proper access control for all operations
✅ **Single System Wallet**: All transactions signed by backend
✅ **Stage Validation**: Enforces proper supply chain progression
✅ **Real-time QR Scanning**: Always shows latest blockchain state
✅ **Production Ready**: Proper error handling and logging
✅ **Easy Installation**: Multiple installation options with fallbacks