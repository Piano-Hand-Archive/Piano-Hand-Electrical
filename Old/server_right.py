import asyncio
import time
from bleak import BleakClient, BleakScanner

# MATCHED TO ESP32
CHAR_UUID = "19b10002-e8f2-537e-4f6c-d104768a1215"
FILE_NAME = "hotcrossbuns.txt"

async def play_song(client, lines):
    print("\n--- Starting Song ---")
    start_time = time.perf_counter()

    for line in lines:
        parts = line.split(":")
        try:
            # Assumes format: timestamp:command:value
            target_time = float(parts[0]) / 1000.0 # Convert ms to seconds
        except:
            continue
            
        # Precise wait
        while (time.perf_counter() - start_time) < target_time:
            await asyncio.sleep(0.001)

        await client.write_gatt_char(CHAR_UUID, line.encode())
        print(f"Sent: {line}")

    print("\nSong Finished. Resetting...")
    await client.write_gatt_char(CHAR_UUID, b"0:RESET:0")

async def main():
    print("Searching for ESP32-Piano...")
    device = await BleakScanner.find_device_by_name("ESP32-Piano-Right")

    if not device:
        print("Could not find ESP32. Ensure it is powered and advertising.")
        return

    async with BleakClient(device) as client:
        print("Connected.")
        
        try:
            with open(FILE_NAME, "r") as f:
                lines = [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            print(f"Error: {FILE_NAME} not found.")
            return

        while True:
            choice = input(f"Press 'y' to play, or 'q' to quit: ").lower()
            if choice == 'y':
                await play_song(client, lines)
            elif choice == 'q':
                break

if __name__ == "__main__":
    asyncio.run(main())