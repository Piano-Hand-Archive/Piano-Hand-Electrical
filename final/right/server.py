import asyncio
import time
from bleak import BleakClient, BleakScanner

# Must match ESP32 UUIDs, Changed to ...1215
CHAR_UUID = "19b10002-e8f2-537e-4f6c-d104768a1215"

async def play_song(client, lines):
    print("\n--- Starting Song ---")
    start_time = time.perf_counter()

    for line in lines:
        try:
            target_time = float(line.split(":")[0])
        except:
            continue
            
        # Precise wait for timestamp
        while (time.perf_counter() - start_time) < target_time:
            await asyncio.sleep(0.001)

        await client.write_gatt_char(CHAR_UUID, line.encode())
        print(f"Sent: {line}")

    # Song ended
    print("\nReturning hand to starting position...")
    await client.write_gatt_char(CHAR_UUID, b"RESET")
    await asyncio.sleep(3.0) # Physical buffer for homing

async def main():
    print("Searching for ESP32-Piano...")
    device = await BleakScanner.find_device_by_name("ESP32-Piano")

    if not device:
        print("Could not find ESP32.")
        return

    async with BleakClient(device) as client:
        print("Connected.")
        
        # Load file
        with open(FILE_NAME, "r") as f:
            lines = [line.strip() for line in f if line.strip()]

        while True:
            print("-" * 30)
            choice = input(f"Press 'y' to play {FILE_NAME}, or 'q' to quit: ").lower()
            
            if choice == 'y':
                await play_song(client, lines)
            elif choice == 'q':
                break
            else:
                print("Invalid input.")

if __name__ == "__main__":
    try:
        FILE_NAME = input("Enter the file name:")
        asyncio.run(main())
    except Exception as e:
        print(f"Error: {e}")