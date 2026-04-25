import asyncio
from bleak import BleakScanner, BleakClient

SERVICE_UUID = "6E400001-B5A3-F393-E0A9-E50E24DCCA9E"
RX_UUID      = "6E400002-B5A3-F393-E0A9-E50E24DCCA9E"
TX_UUID      = "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"

def callback(sender, data):
    print(f"\n[SERVER] Received from ESP32: {data.decode()}")

async def main():
    print("Scanning...")
    device = await BleakScanner.find_device_by_name("ESP32-Hand-Tester")
    if not device: return

    async with BleakClient(device) as client:
        print("Connected!")
        await client.start_notify(TX_UUID, callback)
        
        while True:
            val = input("\nEnter finger index to test (0-4) or 'q': ")
            if val == 'q': break
            
            print(f"Triggering finger {val}...")
            await client.write_gatt_char(RX_UUID, f"test:{val}".encode())
            await asyncio.sleep(1.0) # Wait for movement and notification

if __name__ == "__main__":
    asyncio.run(main())