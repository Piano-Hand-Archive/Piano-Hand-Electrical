import asyncio
import time
from bleak import BleakScanner, BleakClient

SERVICE_UUID = "19b10000-e8f2-537e-4f6c-d104768a1214"
RX_UUID      = "19b10001-e8f2-537e-4f6c-d104768a1214"
TX_UUID      = "19b10002-e8f2-537e-4f6c-d104768a1214"

async def send_chunked_data(client, data_string):
    """Splits a string into 20-byte chunks to bypass BLE limits safely."""
    chunk_size = 20
    payload = data_string + "\n" 
    
    for i in range(0, len(payload), chunk_size):
        chunk = payload[i:i+chunk_size]
        await client.write_gatt_char(RX_UUID, chunk.encode("utf-8"), response=True)
        await asyncio.sleep(0.05) 

async def main():
    print("Scanning for ESP32-BLE-Control...")
    device = await BleakScanner.find_device_by_name("ESP32-BLE-Control")
    if not device:
        print("ESP32 not found. Make sure it's powered and advertising.")
        return

    async with BleakClient(device) as client:
        print("Connected to ESP32!")
        
        try:
            with open("hotcrossbuns.txt", "r") as f:
                lines = [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            print("Error: Could not find 'hotcrossbuns.txt'")
            return

        print(f"Successfully loaded {len(lines)} commands.\n")
        
        while True:
            start_time = time.time()
            
            for line in lines:
                # Extract the timestamp (e.g., "1.000" from "1.000:servo:1")
                parts = line.split(":", 1)
                if len(parts) < 2: continue
                
                try:
                    target_timestamp = float(parts[0])
                except ValueError:
                    continue # Skip malformed lines

                # 1. Wait until the correct time to send
                target_time_abs = start_time + target_timestamp
                sleep_duration = target_time_abs - time.time()
                if sleep_duration > 0:
                    await asyncio.sleep(sleep_duration)
                
                # 2. Send the exact line to the ESP32
                print(f"[{target_timestamp:.3f}s] Sending: {line}")
                await send_chunked_data(client, line)
                
                # 3. Wait for the ESP32 to finish the physical movement
                await asyncio.sleep(0.1) # Give ESP32 time to switch to BUSY state
                while True:
                    status = await client.read_gatt_char(TX_UUID)
                    if status.decode('utf-8') == "READY":
                        break
                    await asyncio.sleep(0.05)
                    
            print("\nSong complete!")
            repeat = input("Play again? (y/n): ").strip().lower()
            if repeat != 'y':
                break

if __name__ == "__main__":
    asyncio.run(main())