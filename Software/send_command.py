import asyncio
from bleak import BleakClient, BleakScanner

# UUIDs must match the ESP32 script
SERVICE_UUID = "19b10000-e8f2-537e-4f6c-d104768a1214"
CHAR_UUID = "19b10002-e8f2-537e-4f6c-d104768a1214"

async def main():
    print("Scanning for ESP32-BLE-Control...")
    device = await BleakScanner.find_device_by_name("ESP32-BLE-Control")

    if not device:
        print("ESP32 not found. Make sure it's powered and advertising.")
        return

    async with BleakClient(device) as client:
        print("==== Piano Hand Stepper Control (1~5 Octaves) ====")
        print("Usage: Enter current and target note names (e.g., C1, E3)")
        print("Example: (C1,C2) / (Current, Target) → Rotate accordingly\n")

        while True:
            cmd = input("Command: ").strip()
            if cmd.lower() == "exit":
                break
            if not cmd.startswith("(") or not cmd.endswith(")"):
                print("Invalid format. Use (C1,D2)")
                continue
            await client.write_gatt_char(CHAR_UUID, cmd.encode("utf-8"))
            print(f"Sent → {cmd}")

if __name__ == "__main__":
    asyncio.run(main())