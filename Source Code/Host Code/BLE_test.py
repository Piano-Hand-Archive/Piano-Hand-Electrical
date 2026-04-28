import asyncio
from bleak import BleakScanner, BleakClient

# Must match the RX UUID in the ESP32 code
UART_RX_UUID = "6E400002-B5A3-F393-E0A9-E50E24DCCA9E"

async def run_test():
    print("Scanning for ESP-Test...")
    device = await BleakScanner.find_device_by_name("ESP-Test")
    
    if not device:
        print("Could not find ESP32. Make sure it's powered on.")
        return

    async with BleakClient(device) as client:
        print(f"Connected to {device.name}!")
        
        for i in range(5):
            msg = f"Test Message {i}"
            print(f"Sending: {msg}")
            await client.write_gatt_char(UART_RX_UUID, msg.encode())
            await asyncio.sleep(1)
            
        print("Test complete. Disconnecting...")

if __name__ == "__main__":
    asyncio.run(run_test())