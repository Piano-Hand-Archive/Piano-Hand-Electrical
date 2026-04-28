import asyncio
import time
from bleak import BleakClient, BleakScanner

CHAR_UUID = "19b10002-e8f2-537e-4f6c-d104768a1214"
FILE_NAME = "test.txt"

async def play_song(client, lines):
    print("\n--- Starting Playback ---")
    start_time = time.perf_counter()
    active_fingers = []

    for i in range(len(lines)):
        parts = lines[i].strip().split(":")
        if len(parts) < 3: continue
        
        target_time = float(parts[0])
        cmd, val = parts[1], parts[2]

        # Wait until the timestamp in the file is reached
        while (time.perf_counter() - start_time) < target_time:
            await asyncio.sleep(0.001)

        # RELEASE: Lift any finger that was previously pressed
        # This happens exactly at the arrival of the next timestamp
        for finger in active_fingers:
            await client.write_gatt_char(CHAR_UUID, f"0:release:{finger}".encode())
        active_fingers = []

        # EXECUTE: Press new finger or move stepper
        if cmd == "servo":
            await client.write_gatt_char(CHAR_UUID, f"{target_time}:press:{val}".encode())
            active_fingers.append(val)
        else:
            await client.write_gatt_char(CHAR_UUID, lines[i].encode())
            
        print(f"Time {target_time}: {cmd} {val}")

    await client.write_gatt_char(CHAR_UUID, b"RESET")

async def main():
    print("Searching for ESP32-Piano...")
    device = await BleakScanner.find_device_by_name("ESP32-Piano")
    if not device: return

    async with BleakClient(device) as client:
        with open(FILE_NAME, "r") as f:
            lines = [line.strip() for line in f if line.strip()]
        while True:
            if input("Press 'y' to play: ").lower() == 'y':
                await play_song(client, lines)
            else: break

if __name__ == "__main__":
    asyncio.run(main())