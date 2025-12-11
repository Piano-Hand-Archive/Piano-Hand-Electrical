import asyncio
from bleak import BleakClient, BleakScanner

CHAR_UUID = "19b10002-e8f2-537e-4f6c-d104768a1214"

async def main():
    print("Scanning for ESP32-Servo...")
    device = await BleakScanner.find_device_by_name("ESP32-Servo")

    if not device:
        print("ESP32 not found.")
        return

    async with BleakClient(device) as client:
        print("Connected. Type 'servo' to run 90° sweep, or 'exit' to quit.")

        while True:
            cmd = input("Command: ").strip()
            if cmd.lower() == "exit":
                break

            await client.write_gatt_char(CHAR_UUID, cmd.encode())
            print("Sent:", cmd)

if __name__ == "__main__":
    asyncio.run(main())
