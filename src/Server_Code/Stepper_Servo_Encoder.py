import asyncio
from bleak import BleakScanner, BleakClient

SERVICE_UUID = "19b10000-e8f2-537e-4f6c-d104768a1214"
CHAR_UUID    = "19b10002-e8f2-537e-4f6c-d104768a1214"

def validate_commands(lines):
    """Validates the syntax of the commands before sending anything to the ESP32."""
    if len(lines) % 2 != 0:
        print("Warning: Odd number of lines in file. The last dangling line will be ignored.")

    valid_pairs = []
    for i in range(0, len(lines) - 1, 2):
        move_cmd = lines[i]
        play_cmd = lines[i+1]

        # Check Move Command (Expected: Note1,Note2,Offset1,Offset2,Offset3,Offset4,Offset5)
        if len(move_cmd.split(",")) != 7:
            print(f"Validation Error on line {i+1}: '{move_cmd}'")
            print(" -> Expected 7 parts separated by commas (e.g., C4,E4,0,0,0,0,0).")
            return None

        # Check Play Command (Expected: Finger,Duration OR Finger,Duration;Finger,Duration)
        for chord in play_cmd.split(";"):
            if len(chord.split(",")) != 2:
                print(f"Validation Error on line {i+2}: '{play_cmd}'")
                print(" -> Expected format 'Finger,Duration' separated by semicolons (e.g., 1,1.2).")
                return None
                
            # Basic type checking for finger (int) and duration (float)
            try:
                f_num, dur = chord.split(",")
                int(f_num)
                float(dur)
            except ValueError:
                print(f"Validation Error on line {i+2}: '{play_cmd}'")
                print(" -> Finger must be an integer and Duration must be a number.")
                return None

        valid_pairs.append((move_cmd, play_cmd))
        
    return valid_pairs

async def main():
    print("Scanning for ESP32-BLE-Control...")
    device = await BleakScanner.find_device_by_name("ESP32-BLE-Control")
    if not device:
        print("ESP32 not found. Make sure it's powered and advertising.")
        return

    async with BleakClient(device) as client:
        print("Connected to ESP32!")
        
        try:
            with open("hotcrossbuns.txt", "r") as f:
                # Read all non-empty lines
                lines = [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            print("Error: Could not find 'hotcrossbuns.txt' in the current directory.")
            return

        # Run the validation check
        commands = validate_commands(lines)
        if not commands:
            print("\nAborting playback due to validation errors. Please fix your text file.")
            return

        print(f"Successfully loaded and validated {len(commands)} note commands.\n")
        
        # Playback Loop
        while True:
            print("Starting playback...\n")
            
            for move_cmd, play_cmd in commands:
                # Combine into a single payload separated by "|"
                packet = f"{move_cmd}|{play_cmd}"
                
                print(f"Sending: {packet}")
                await client.write_gatt_char(CHAR_UUID, packet.encode("utf-8"))
                
                # Handshake: Wait for ESP32 to finish the physical movement
                await asyncio.sleep(0.5) # Give ESP32 a moment to trigger BUSY state
                while True:
                    status = await client.read_gatt_char(CHAR_UUID)
                    if status.decode('utf-8') == "READY":
                        break
                    await asyncio.sleep(0.1) # Poll every 100ms
                    
            print("\nSong complete!")
            
            # Ask the user if they want to loop
            repeat = input("Would you like to play the sequence again? (y/n): ").strip().lower()
            if repeat != 'y':
                print("Disconnecting and exiting. Goodbye!")
                break
            else:
                print("\nRestarting sequence...")

if __name__ == "__main__":
    asyncio.run(main())