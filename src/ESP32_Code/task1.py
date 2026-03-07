import asyncio
import csv
from bleak import BleakScanner, BleakClient

SERVICE_UUID  = "19b10000-e8f2-537e-4f6c-d104768a1214"
CHAR_UUID     = "19b10002-e8f2-537e-4f6c-d104768a1214"
NOTIFY_UUID   = "19b10003-e8f2-537e-4f6c-d104768a1214"  # For ACK (needs to be added to ESP32 as well)

def load_commands(csv_path):
    """Reads a CSV file and converts it into a BLE command list"""
    commands = []
    with open(csv_path, newline='') as f:
        rows = [r for r in csv.DictReader(f) if r['L_Notes'].strip()]

    for i, row in enumerate(rows):
        curr_note = row['L_Notes'].strip()
        prev_note = rows[i-1]['L_Notes'].strip() if i > 0 else curr_note

        # Extract digits only from special commands like "4b+"
        raw_cmd = row['L_Commands'].strip()
        finger_num = int(''.join(filter(str.isdigit, raw_cmd)))
        is_black_key = 'b' in raw_cmd  # Check if it's a black key

        # Calculate delay (beat-based)
        curr_time = float(row['Time'])
        prev_time = float(rows[i-1]['Time']) if i > 0 else 0.0
        delay_sec = curr_time - prev_time

        cmd_str = f"({prev_note},{curr_note},{finger_num})"
        if is_black_key:
            cmd_str = f"({prev_note},{curr_note},{finger_num}b)"  # Add black key flag

        commands.append({'cmd': cmd_str, 'delay': delay_sec})

    return commands


async def main():
    CSV_PATH = "fingering_plan.csv"
    commands = load_commands(CSV_PATH)
    print(f"Total {len(commands)} commands loaded successfully\n")
    for c in commands[:5]:  # Preview
        print(f"  Delay {c['delay']:.2f}s → {c['cmd']}")
    print("  ...")

    print("\nScanning for ESP32...")
    device = await BleakScanner.find_device_by_name("ESP32-BLE-Control")
    if not device:
        print("ESP32 not found.")
        return

    ack_event = asyncio.Event()

    def on_notify(sender, data):
        msg = data.decode("utf-8").strip()
        if msg == "OK":
            ack_event.set()

    async with BleakClient(device) as client:
        print("ESP32 connected!")

        # Register notification for receiving ACK
        await client.start_notify(NOTIFY_UUID, on_notify)

        input("\nPress [Enter] to start playback...")

        for i, item in enumerate(commands):
            # Beat delay (skip the first one)
            if i > 0:
                await asyncio.sleep(item['delay'])

            # Send command
            await client.write_gatt_char(CHAR_UUID, item['cmd'].encode("utf-8"))
            print(f"[{i+1:03d}/{len(commands)}] Sent: {item['cmd']}")

            # Wait for ESP32 completion ACK (max 10 seconds)
            try:
                await asyncio.wait_for(ack_event.wait(), timeout=10.0)
                ack_event.clear()
            except asyncio.TimeoutError:
                print(f" Timeout {item['cmd']} - Moving to the next command.")

        print("\nPlayback complete!")
        await client.stop_notify(NOTIFY_UUID)


if __name__ == "__main__":
    asyncio.run(main())