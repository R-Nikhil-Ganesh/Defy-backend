# FreshChain Blockchain Integration

## Real Shardeum Network Configuration

### Network Details
- **RPC URL**: https://api-mezame.shardeum.org/
- **Chain ID**: 8119 (0x1fb7 in hex)
- **Contract Address**: 0x064e8D53bFF8023b0531FE845195c3741790870E
- **Network Name**: Shardeum Testnet

### MetaMask Setup
1. **Add Shardeum Network to MetaMask**:
   - Network Name: `Shardeum Testnet`
   - RPC URL: `https://api-mezame.shardeum.org/`
   - Chain ID: `8119`
   - Currency Symbol: `SHM`
   - Block Explorer: `https://explorer.shardeum.org/`

2. **Admin Login Requirements**:
   - MetaMask must be installed and connected
   - Must be on Shardeum Testnet (Chain ID: 8119)
   - The app will automatically prompt to switch networks

### Smart Contract Functions
The deployed contract supports:
- `createBatch(string _batchId, string _productType)`
- `updateLocation(string _batchId, string _status, string _location)`
- `getBatchDetails(string _batchId)` (view function)
- `reportExcursion(string _batchId, string _alertType, bytes _encryptedSensorData)`

### Backend Configuration
1. **Environment Variables** (create `.env` file):
   ```
   SHARDEUM_RPC_URL=https://api-mezame.shardeum.org/
   CHAIN_ID=8119
   CONTRACT_ADDRESS=0x064e8D53bFF8023b0531FE845195c3741790870E
   SYSTEM_PRIVATE_KEY=your-private-key-here
   ```

2. **For Production**: Replace `SYSTEM_PRIVATE_KEY` with actual private key

### Frontend Configuration
The frontend automatically:
- Detects MetaMask installation
- Prompts network switching to Shardeum
- Handles transaction signing for Admin users
- Shows real transaction hashes and blockchain explorer links

### Demo vs Production Mode
- **Demo Mode**: Uses mock data, no real blockchain calls
- **Production Mode**: Requires `.env` setup with real private key
- **Admin MetaMask**: Always uses real MetaMask for transaction signing

### Transaction Flow
1. **Admin Action** → **MetaMask Signature** → **Blockchain Transaction**
2. **Other Roles** → **Backend API** → **System Wallet** → **Blockchain Transaction**

### Testing
1. **Login as Admin**: `admin` / `demo123` (requires MetaMask)
2. **Create Batch**: Uses MetaMask to sign real blockchain transaction
3. **Update Stage**: Uses MetaMask to sign real blockchain transaction
4. **View on Explorer**: Click transaction hash to view on Shardeum explorer

### Security Notes
- Only Admin users interact with MetaMask
- System private key should be kept secure
- All transactions are recorded on Shardeum blockchain
- Contract address is immutable and verified