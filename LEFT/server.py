import asyncio
import time
from bleak import BleakClient, BleakScanner

CHAR_UUID = "19b10002-e8f2-537e-4f6c-d104768a1215"

async def play_song(client, lines):
    print("\n--- Starting Left Hand Performance ---")
    start_time = time.perf_counter()
    
    for line in lines:
        parts = line.split(":")
        target_time = float(parts[0]) / 1000.0
        
        while (time.perf_counter() - start_time) < target_time:
            await asyncio.sleep(0.001)

        cmd = parts[1]
        val = parts[2]

        if cmd == "step":
            # val should be the number of keys to move (e.g., "5" or "-3")
            await client.write_gatt_char(CHAR_UUID, f"0:step:{val}".encode())
        
        elif cmd == "servo":
            finger = val
            # Standard piano "hit" logic
            await client.write_gatt_char(CHAR_UUID, f"0:servo_on:{finger}".encode())
            await asyncio.sleep(0.15) # Hold down duration
            await client.write_gatt_char(CHAR_UUID, f"0:servo_off:{finger}".encode())

    print("Song Complete. Resetting Stepper.")
    await client.write_gatt_char(CHAR_UUID, b"RESET")

async def main():
    print("Searching for ESP32-Piano-Right...")
    device = await BleakScanner.find_device_by_name("ESP32-Piano-Right")
    
    if not device:
        print("Left Hand ESP32 not found. Check if it is powered on.")
        return

    async with BleakClient(device) as client:
        print("Connected to Left Hand.")
        file_name = input("Enter Left Hand song file: ")
        try:
            with open(file_name, "r") as f:
                lines = [l.strip() for l in f if l.strip()]
            await play_song(client, lines)
        except FileNotFoundError:
            print("File not found.")

if __name__ == "__main__":
    asyncio.run(main())