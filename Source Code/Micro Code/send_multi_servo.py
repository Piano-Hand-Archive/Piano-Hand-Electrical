import asyncio
import json
from bleak import BleakClient, BleakScanner

CHAR_UUID = "19b10002-e8f2-537e-4f6c-d104768a1214"

async def main():
    print("Scanning for ESP32-MultiServo...")
    device = await BleakScanner.find_device_by_name("ESP32-MultiServo")

    if not device:
        print("ESP32 not found.")
        return

    async with BleakClient(device) as client:
        print("Connected. Example commands:")
        print("  [1]")
        print("  [1,2]")
        print("  [2]\n")
        print("Type 'exit' to quit.\n")

        while True:
            cmd = input("Servo list: ").strip()
            if cmd.lower() == "exit":
                break

            try:
                # Validate JSON list before sending
                lst = json.loads(cmd)
                if not isinstance(lst, list):
                    print("Enter a list like [1,2]")
                    continue
            except:
                print("Invalid format. Use JSON list like [1,2]")
                continue

            await client.write_gatt_char(CHAR_UUID, cmd.encode())
            print("Sent:", cmd)

if __name__ == "__main__":
    asyncio.run(main())
