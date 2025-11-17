import asyncio
from bleak import BleakClient, BleakScanner

SERVICE_UUID = "19b10000-e8f2-537e-4f6c-d104768a1214"
CHAR_UUID    = "19b10002-e8f2-537e-4f6c-d104768a1214"
TXT_FILE = "hot_cross_buns.txt"

async def main():
    print("Scanning for ESP32-BLE-Control...")
    device = await BleakScanner.find_device_by_name("ESP32-BLE-Control")
    if not device:
        print("ESP32 not found.")
        return

    async with BleakClient(device) as client:
        input("Press Enter to send all commands from the .txt file...")
        with open(TXT_FILE, "r") as f:
            for line in f:
                cmd = line.strip()
                if not cmd:
                    continue
                await client.write_gatt_char(CHAR_UUID, cmd.encode("utf-8"))
                print(f"Sent: {cmd}")
                await asyncio.sleep(0.1)  # slight delay to avoid BLE buffer overflow

if __name__ == "__main__":
    asyncio.run(main())
