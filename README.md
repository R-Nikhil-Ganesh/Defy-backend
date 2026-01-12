# FreshChain Backend API

FastAPI backend service that handles all blockchain operations for the FreshChain dApp. This backend acts as the system layer between the frontend and the Shardeum blockchain.

## Features

- **Role-aware supply chain flows** with explicit producer, transporter, retailer, consumer, and admin capabilities
- **Sensor orchestration** for transporter vehicles and retailer stores, including QR-based binding and telemetry history
- **Hybrid ML shelf-life analytics** that mix Arrhenius physics, joblib regression, and blockchain-linked sensor data
- **CNN freshness scans** wired to the provided fruit/veg model so producers and retailers can validate batches visually
- **Shardeum-native blockchain abstraction** with optimized gas controls and event hydration
- **Companion simulators** for quick transporter/retailer sensor testing without hardware

## Quick Start

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Place ML Assets**
   - `../fruit-veg-freshness-ai-main/rottenvsfresh98pval.h5` (CNN for image scans)
   - `../freshness/shelf_life_model.pkl` and `prediction_history.json`
   - Override locations through `SHELF_LIFE_MODEL_PATH`, `FRESHNESS_MODEL_PATH`, and `SHELF_LIFE_HISTORY_PATH` in `.env` if your paths differ.

3. **Environment Setup**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

4. **Configure Environment Variables**
   - `SYSTEM_PRIVATE_KEY`: Your admin wallet private key
   - `CONTRACT_ADDRESS`: Deployed FreshChain contract address
   - `SHARDEUM_RPC_URL`: Shardeum network RPC endpoint
   - `SENSOR_STATE_PATH`, `QR_CACHE_DIR`: Optional overrides for sensor/QR persistence

5. **Run the Server**
   ```bash
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

6. **API Documentation**
   - Swagger UI: http://localhost:8000/docs
   - ReDoc: http://localhost:8000/redoc

## API Endpoints

### Batch Management (Retailer/Admin)

- `POST /batch/create` - Create new batch
- `POST /batch/update-stage` - Update batch stage/location
- `POST /batch/report-alert` - Report alerts/excursions

### Consumer Audit (Read-only)

- `GET /batch/{batchId}` - Get batch details for QR scan

### System

- `GET /health` - Health check and blockchain status
- `GET /` - API info

### Sensor + QR Workflows

- `POST /sensors/register` - Register transporter or retailer sensors
- `POST /qr/scan` - Bind a sensor to a batch by scanning QR
- `POST /sensors/data` - Push temperature/humidity readings
- `GET /sensors/batch/{batchId}` - Inspect last readings for a batch

### ML + Analytics

- `POST /ml/freshness-scan` - Run CNN freshness classification on sample images
- `POST /ml/shelf-life` - Generate Arrhenius + ML shelf-life predictions with sensor context

## Sensor Simulators

Two utility scripts mimic hardware sensors:

```bash
# Transporter (links vehicle probes)
python simulators/transporter_sensor_sim.py --batch-id Demo-001 --token transporter

# Retailer (links in-store sensors)
python simulators/retailer_sensor_sim.py --batch-id Demo-001 --token retailer
```

Both scripts expect you to log in through `/auth/login` first and reuse the demo username (token) in lieu of JWT. Override `--base-url`, `--sensor-id`, or `--interval` as needed when pointing to remote deployments.

## Project Structure

```
Backend FreshChain/
├── main.py              # FastAPI application entry point
├── blockchain.py        # Blockchain service and Web3 integration
├── schemas.py           # Pydantic models for requests/responses
├── config.py            # Configuration and environment variables
├── contracts/           # Smart contract ABI files
│   └── FreshChain.json
├── requirements.txt     # Python dependencies
├── .env.example        # Environment variables template
└── README.md           # This file
```

## Security Notes

- Never commit real private keys to version control
- Use environment variables for sensitive configuration
- The system wallet should have sufficient funds for gas fees
- Consider using a hardware wallet or key management service in production

## Development

The backend is designed to be:
- **Simple**: Minimal complexity, focused on core functionality
- **Fast**: Direct blockchain calls without unnecessary overhead
- **Demo-safe**: Reliable for demonstrations and testing
- **Production-ready**: Proper error handling and logging

## Blockchain Integration

- **Network**: Shardeum Testnet
- **Library**: Web3.py for Ethereum-compatible interactions
- **Gas Management**: Configurable gas limits and pricing
- **Transaction Handling**: Automatic nonce management and confirmation waiting