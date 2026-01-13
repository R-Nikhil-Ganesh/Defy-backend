# Testing Blockchain Storage & Sensor Auto-Unlinking

## Overview
This guide explains how to test:
1. ✅ Violations are stored in blockchain
2. ✅ Transporter sensor auto-disconnects when retailer links

---

## Quick Test Command

```bash
cd Defy-backend
python test_blockchain_violations.py
```

---

## What Happens

### 1. Blockchain Storage Test

**Process:**
1. Script logs in as transporter
2. Gets current batch details (shows existing alerts)
3. Submits 4 temperature violations (15-18°C when Apple optimal is -1 to 4°C)
4. System calculates 30-minute average
5. If average exceeds range → **Stores alert in blockchain**
6. Script fetches batch details again to verify new alert

**Expected Output:**
```
✅ SUCCESS: Violation was stored in blockchain!

Latest alert:
  Type: Environmental Conditions Violation (30-min Average)
  Data: CRITICAL: Temperature 16.50°C exceeds maximum 4.00°C | Product: Apple...
```

---

### 2. Sensor Auto-Unlinking Test

**Scenario:**
- Transporter sensor `SENSOR-T-006` is monitoring batch during transit
- Retailer receives the batch and scans QR code
- Retailer links their sensor `SENSOR-R-001`
- **System automatically disconnects transporter sensor**

**How to Test:**

1. **Setup - Link Transporter Sensor:**
   ```bash
   # Start simulator (links transporter sensor)
   cd Defy-backend
   python simulate_transporter_sensors.py
   ```

2. **Verify Transporter Link:**
   ```
   GET /sensors/SENSOR-T-006/binding
   Response: { "batchId": "APPLE-001", "locationType": "transporter" }
   ```

3. **Retailer Scan:**
   - Login as retailer in frontend
   - Go to Consumer Audit page
   - Scan batch QR code (or enter batch ID)
   - Click "Select Sensor to Monitor"
   - Select a RETAILER sensor (e.g., SENSOR-R-001)

4. **Verify Auto-Unlinking:**
   ```
   GET /sensors/SENSOR-T-006/binding
   Response: 404 (sensor no longer linked)
   
   GET /sensors/SENSOR-R-001/binding
   Response: { "batchId": "APPLE-001", "locationType": "retailer" }
   ```

**What Happens in Backend:**
```python
# When retailer links their sensor:
async def link_sensor(sensor_id, batch_id, location_type="retailer"):
    # 1. Check if another retailer sensor was linked
    existing_binding = batch_links.get("retailer")
    
    # 2. Unlink the old sensor for this location type
    if existing_binding:
        old_sensor_id = existing_binding["sensorId"]
        unlink(old_sensor_id)  # ← SENSOR-R-XXX disconnected
    
    # 3. Link the new sensor
    link(sensor_id, batch_id, "retailer")
```

**Note:** Transporter and Retailer can coexist, but only ONE sensor per type per batch.

---

## Backend Logs

When violations occur, you'll see:
```
INFO: Batch APPLE-001: 30-min avg = 16.50°C, 75.00% (based on 4 readings)
WARNING: 30-min average violation reported to blockchain for batch APPLE-001: Temperature 16.50°C exceeds maximum 4.00°C | Humidity 75.00% is below minimum 90.00%
INFO: Alert reported for batch APPLE-001 by transporter
```

When sensor unlinking occurs:
```
INFO: Auto-unlinked SENSOR-T-006 from batch APPLE-001 (transporter)
INFO: Linked SENSOR-R-001 to batch APPLE-001 (retailer) by retailer_user
```

---

## Troubleshooting

### No Violations Detected?

**Possible reasons:**

1. **Sensor not linked**
   - Solution: Link sensor via QR scan first
   - Check: `GET /sensors/{sensor_id}/binding`

2. **Not enough readings**
   - Need minimum 3 readings for 30-min average
   - Solution: Run simulator longer or submit more readings

3. **Values within range**
   - Apple range: -1 to 4°C, 90-95% humidity
   - Submit values like 15°C or 60% humidity to trigger violations

4. **Blockchain not connected**
   - Check backend logs for connection errors
   - Verify `BLOCKCHAIN_ENABLED=true` in config

### Sensor Still Linked After Retailer Scan?

1. **Check sensor type mismatch:**
   - Transporter can only link transporter sensors
   - Retailer can only link retailer sensors
   
2. **Verify retailer used correct sensor:**
   ```python
   # In Consumer Audit:
   # - Available sensors shown are filtered by user role
   # - Retailer sees: SENSOR-R-001, SENSOR-R-002, etc.
   # - Transporter sees: SENSOR-T-006, SENSOR-T-007, etc.
   ```

---

## API Endpoints Reference

### Get Batch Details (with alerts)
```
GET /batch/{batch_id}
Authorization: Bearer {token}

Response:
{
  "batchId": "APPLE-001",
  "productType": "apple",
  "currentStage": "In Transit",
  "alerts": [
    {
      "alertType": "Environmental Conditions Violation (30-min Average)",
      "encryptedData": "CRITICAL: Temperature 16.50°C exceeds...",
      "timestamp": "2026-01-13T10:30:00Z",
      "transactionHash": "0xabc123..."
    }
  ]
}
```

### Get Sensor Binding
```
GET /sensors/{sensor_id}/binding
Authorization: Bearer {token}

Response:
{
  "sensorId": "SENSOR-T-006",
  "batchId": "APPLE-001",
  "locationType": "transporter",
  "linkedAt": "2026-01-13T09:00:00Z",
  "linkedBy": "transporter"
}
```

### Submit Sensor Reading
```
POST /sensors/data
Authorization: Bearer {token}

Body:
{
  "sensorId": "SENSOR-T-006",
  "temperature": 15.0,
  "humidity": 60.0
}

Response:
{
  "batchId": "APPLE-001",
  "samples": 4,
  "latest": { "temperature": 15.0, "humidity": 60.0 }
}
```

---

## Expected Test Results

✅ **Blockchain Storage:**
- Violations appear in batch alerts array
- Each alert has transaction hash
- Alert data includes average values and expected ranges

✅ **Sensor Auto-Unlinking:**
- Old location type sensor disconnects when new one links
- GET binding returns 404 for unlinked sensor
- Simulator shows "not linked" warning after unlinking

✅ **30-Minute Average:**
- System requires 3+ readings before checking
- Individual spikes don't trigger alerts
- Only sustained violations (30-min avg) reported to blockchain
