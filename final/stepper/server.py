import asyncio
from bleak import BleakScanner, BleakClient

# Use your existing UUIDs
RX_UUID = "19b10001-e8f2-537e-4f6c-d104768a1214"

async def main():
    print("Searching for ESP32...")
    device = await BleakScanner.find_device_by_name("ESP32-BLE-Control")
    if not device:
        print("Device not found.")
        return

    async with BleakClient(device) as client:
        print("Connected! Press ENTER to rotate the motor (or 'q' to quit).")
        
        while True:
            user_input = input(">>> ")
            if user_input.lower() == 'q':
                break
            
            # Simple command format that matches your ESP32 parsing logic
            # format: timestamp:type:key (we use dummy values)
            command = "0.000:step:C1-C2" 
            
            print("Sending rotation command...")
            await client.write_gatt_char(RX_UUID, (command + "\n").encode())
            
            # Brief pause to prevent overlapping commands
            await asyncio.sleep(0.5)

if __name__ == "__main__":
    asyncio.run(main())