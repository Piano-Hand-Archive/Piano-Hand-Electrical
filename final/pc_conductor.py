"""
PC Conductor (v2) - BLE Central for ESP32 Piano Player

Calibration flow (user-driven):
  1) "Which key is it on currently?" (Rightmost candidate, e.g., C5)
  2) Input JOG angle -> Robot moves
  3) "Which key is it on after moving?" (e.g., A4)
  -> Automatically reverse-calculates step_degrees including the sign (+/-)
  4) Confirm Home (Rightmost end)
  5) Servo OPEN/CLOSE PWM 5-channel calibration
  6) Start performance via CSV

CSV Interpretation:
  - 'key' = Note name the stepper will move to (Jaemin's definition)
  - 'finger' = Servo number to press (1~5)
  - 'thumb_pos' column is not used
  - If there are multiple fingers at the same (timestamp, key), they will be pressed simultaneously
"""
import asyncio
import time
import csv
from collections import OrderedDict
from bleak import BleakScanner, BleakClient

# ============================================================
# CONFIG
# ============================================================
DEVICE_NAME = "ESP32-Piano"
RX_UUID = "19b10001-e8f2-537e-4f6c-d104768a1214"
TX_UUID = "19b10002-e8f2-537e-4f6c-d104768a1214"

CSV_PATH = "fingering_plan.csv"
INCLUDE_LEFT_HAND = False   # If changed to True, 'L' rows are processed identical to the right hand
CHUNK_SIZE = 20

# ============================================================
# KEY NAME <-> INDEX
# ============================================================
# White-key indexing that matches the CSV's thumb_pos values.
# Verified: D4 -> 29, G4 -> 32, G2 -> 18, D5 -> 36
# Formula: idx = octave*7 + {C:0, D:1, E:2, F:3, G:4, A:5, B:6}
NOTE_OFFSET = {'C': 0, 'D': 1, 'E': 2, 'F': 3, 'G': 4, 'A': 5, 'B': 6}
NOTE_NAMES  = 'CDEFGAB'

def key_to_idx(name):
    name = name.strip().upper()
    if len(name) < 2 or name[0] not in NOTE_OFFSET:
        raise ValueError(f"Invalid note name: {name}")
    octave = int(name[1:])
    return octave * 7 + NOTE_OFFSET[name[0]]

def idx_to_key(idx):
    return f"{NOTE_NAMES[idx % 7]}{idx // 7}"

# ============================================================
# ASYNC INPUT HELPER
# ============================================================
async def ainput(prompt=""):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, input, prompt)

# ============================================================
# BLE TRANSPORT
# ============================================================
async def send_cmd(client, cmd, timeout_s=20.0):
    payload = (cmd + "\n").encode('utf-8')
    for i in range(0, len(payload), CHUNK_SIZE):
        await client.write_gatt_char(RX_UUID, payload[i:i+CHUNK_SIZE], response=True)
        await asyncio.sleep(0.02)
    # Wait for BUSY (up to 1s); if READY seen first, command was instant.
    busy_seen = False
    for _ in range(20):
        await asyncio.sleep(0.05)
        try:
            status = (await client.read_gatt_char(TX_UUID)).decode('utf-8', errors='ignore').strip()
        except Exception:
            continue
        if status == "BUSY":
            busy_seen = True
            break
        if status == "READY":
            return
    if busy_seen:
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            await asyncio.sleep(0.05)
            try:
                status = (await client.read_gatt_char(TX_UUID)).decode('utf-8', errors='ignore').strip()
            except Exception:
                continue
            if status == "READY":
                return
        print(f"  [WARN] timeout after: {cmd}")

# ============================================================
# CSV LOADING
# ============================================================
def load_csv(path, include_left=False):
    """Returns raw list [(t, key, finger)], min_key, max_key."""
    raw = []
    keys = set()
    with open(path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['hand'] == 'L' and not include_left:
                continue
            try:
                t = float(row['start_time'])
                k = row['key'].strip()
                f_ = int(row['finger'])
                _ = key_to_idx(k)  # validate
            except Exception:
                continue
            raw.append((t, k, f_))
            keys.add(k)
    raw.sort(key=lambda x: (x[0], key_to_idx(x[1]), x[2]))
    if keys:
        sorted_keys = sorted(keys, key=key_to_idx)
        return raw, sorted_keys[0], sorted_keys[-1]
    return raw, None, None

def build_events(raw, home_key):
    """(t, key, finger)* ->  (t, rel_idx, [fingers], duration)*
    rel_idx = home_idx - key_idx. Positive = Left direction from home (lower notes).
    """
    home_idx = key_to_idx(home_key)
    groups = OrderedDict()
    for t, k, f_ in raw:
        rel = home_idx - key_to_idx(k)
        groups.setdefault((t, rel), []).append(f_)
    items = list(groups.items())
    out = []
    for i, ((t, rel), fingers) in enumerate(items):
        if i + 1 < len(items):
            dur = items[i+1][0][0] - t
            dur = max(0.2, min(dur, 1.0))
        else:
            dur = 0.5
        out.append((t, rel, fingers, dur))
    return out

# ============================================================
# CALIBRATION
# ============================================================
def hline(): print("-" * 64)
def header(s):
    print(); hline(); print(f"  {s}"); hline()

async def calibrate_stepper(client, suggested_home):
    """Interactive stepper calibration.
    Returns (home_key, signed_step_deg)."""
    header("STEP 1  Set Home (Rightmost Key)")
    print(f"  The rightmost key in the CSV is '{suggested_home}'.")
    print(f"  Please position the robot hand on '{suggested_home}' or further to the right.")
    print("  Fine-tuning is possible using JOG commands.\n")

    home_key = None
    while True:
        s = (await ainput("Current key the robot hand is on (e.g., C5): ")).strip()
        try:
            key_to_idx(s)
        except Exception as e:
            print(f"  {e}")
            continue
        while True:
            c = (await ainput(f"  Confirm '{s}' as Home? [y=Confirm, j=JOG tune, n=Retry]: ")).strip().lower()
            if c == 'y':
                home_key = s
                await send_cmd(client, "CAL:SET_HOME")
                print(f"  ✓ Home = {home_key}")
                break
            elif c == 'j':
                while True:
                    j = (await ainput("    JOG Angle (Number, Empty=Exit): ")).strip()
                    if not j:
                        break
                    try:
                        await send_cmd(client, f"CAL:JOG:{float(j)}")
                    except ValueError:
                        print("    Numbers only")
                # Break to outer loop to ask for current position again after JOG
                break
            elif c == 'n':
                break
            else:
                print("  y / j / n")
        if home_key is not None:
            break

    # ---------------------------------
    header("STEP 2  Measure step_degrees")
    print("  Move the robot using JOG, and enter the destination key.")
    print("  The step_degrees and rotation direction (sign) will be calculated automatically.\n")

    signed_step = None
    while True:
        while True:
            s = (await ainput("  Enter JOG Angle (e.g., -60 or 45): ")).strip()
            try:
                jog_deg = float(s)
                break
            except ValueError:
                print("  Numbers only")
        await send_cmd(client, f"CAL:JOG:{jog_deg}")

        while True:
            new_name = (await ainput("  Key reached after moving (e.g., A4): ")).strip()
            try:
                new_idx = key_to_idx(new_name)
                break
            except Exception as e:
                print(f"  {e}")

        home_idx = key_to_idx(home_key)
        diff = home_idx - new_idx   # +: new is lower than home (left)
        if diff == 0:
            print("  Same position. Move further and measure again.")
            continue

        signed_step = jog_deg / diff
        print(f"  → Moved {abs(jog_deg):.2f} degrees, key difference is {abs(diff)} steps")
        print(f"  → step_degrees = {signed_step:+.4f}  (Rotation angle per index +1)")
        await send_cmd(client, f"CAL:SET_STEP:{signed_step:.6f}")

        # Restore physical position to home by reverse JOG
        # (current_deg remains 0 on the ESP32, physical must also return to home to sync)
        print("  → Physically returning to Home...")
        await send_cmd(client, f"CAL:JOG:{-jog_deg}")

        c = (await ainput("  Measure again? [y=Retry, Enter=Confirm]: ")).strip().lower()
        if c != 'y':
            break

    # ---------------------------------
    header("STEP 3  Verify Calibration")
    print("  Movement test to a random key. Press Enter to skip.\n")
    while True:
        s = (await ainput("  Key to test movement (e.g., A4, Enter=Exit): ")).strip()
        if not s:
            break
        try:
            tgt_idx = key_to_idx(s)
        except Exception:
            print("  Invalid format")
            continue
        rel = key_to_idx(home_key) - tgt_idx
        await send_cmd(client, f"CAL:GOTO:{rel}")
        actual = (await ainput(f"    Actually reached key (Expected {s}, Enter=OK): ")).strip()
        if actual and actual != s:
            try:
                actual_rel = key_to_idx(home_key) - key_to_idx(actual)
                if actual_rel != 0:
                    new_step = signed_step * (rel / actual_rel)
                    print(f"    Re-tuned step_degrees = {new_step:+.4f}")
                    signed_step = new_step
                    await send_cmd(client, f"CAL:SET_STEP:{signed_step:.6f}")
            except Exception:
                pass
        # Return to Home
        await send_cmd(client, "CAL:GOTO:0")

    print(f"\n  Final: Home={home_key}, step_degrees={signed_step:+.4f}")
    return home_key, signed_step

async def calibrate_servos(client):
    header("STEP 4  Servo PWM Calibration (Ch 0~4)")
    print("  Adjust the OPEN (release) / CLOSE (press) PWM values for each finger.")
    print("  Standard values: OPEN≈205 (1.0ms), CLOSE≈410 (2.0ms)")
    print("  The current defaults of 150/500 are extreme and servos might not move, adjustment is recommended.\n")

    for ch in range(5):
        print(f"-- Channel {ch} (Finger {ch+1}) --")
        opw, cpw = 150, 500
        while True:
            await send_cmd(client, f"CAL:SET_SERVO:{ch}:{opw}:{cpw}")
            await send_cmd(client, f"CAL:TEST_SERVO:{ch}:OPEN")
            s = (await ainput(f"  OPEN PWM (Current {opw}, Number=Change, Enter=Keep): ")).strip()
            if not s:
                break
            try:
                opw = int(s)
            except ValueError:
                print("  Numbers only")
        while True:
            await send_cmd(client, f"CAL:SET_SERVO:{ch}:{opw}:{cpw}")
            await send_cmd(client, f"CAL:TEST_SERVO:{ch}:CLOSE")
            s = (await ainput(f"  CLOSE PWM (Current {cpw}, Number=Change, Enter=Keep): ")).strip()
            if not s:
                break
            try:
                cpw = int(s)
            except ValueError:
                print("  Numbers only")
        await send_cmd(client, f"CAL:TEST_SERVO:{ch}:OPEN")
        print(f"  ✓ Channel {ch}: OPEN={opw}, CLOSE={cpw}\n")

# ============================================================
# PERFORM
# ============================================================
async def perform(client, events, home_key):
    print(f"\n=== Performance Started — {len(events)} events, Home={home_key} ===")
    start = time.time()
    skipped = 0
    for t, rel, fingers, dur in events:
        if rel < 0:
            skipped += 1
            continue
        target_abs = start + t
        now = time.time()
        if target_abs > now:
            await asyncio.sleep(target_abs - now)
        fstr = ','.join(str(f) for f in fingers)
        cmd = f"PLAY:{rel}|{fstr};{dur:.3f}"
        print(f"  [{t:6.2f}s] idx={rel:2d}  fingers={fstr}  dur={dur:.2f}")
        await send_cmd(client, cmd, timeout_s=10.0)
    if skipped:
        print(f"  [WARN] Skipped {skipped} events further right than Home (negative idx)")
    print("=== Performance Finished ===\n")

# ============================================================
# MAIN
# ============================================================
async def main():
    # Read CSV first to check the key range
    raw, min_key, max_key = load_csv(CSV_PATH, INCLUDE_LEFT_HAND)
    if not raw:
        print(f"{CSV_PATH} is empty or unreadable.")
        return

    print("=" * 64)
    print("  ESP32 Piano Conductor v2")
    print("=" * 64)
    print(f"  CSV: {CSV_PATH}  ({len(raw)} rows)")
    print(f"  Key range: {min_key} (Left/Lowest) ~ {max_key} (Right/Highest)")
    print(f"  Recommended Home (Rightmost): {max_key} or higher")

    print(f"\n  Scanning BLE: {DEVICE_NAME}...")
    device = await BleakScanner.find_device_by_name(DEVICE_NAME)
    if not device:
        print(f"  {DEVICE_NAME} not found. Check power/advertising status.")
        return

    async with BleakClient(device) as client:
        print(f"  Connected: {device.address}")
        await asyncio.sleep(0.5)

        # Stepper Calibration
        home_key, signed_step = await calibrate_stepper(client, max_key)

        # Servo Calibration
        do_servo = (await ainput("\nProceed with Servo Calibration? [y/n]: ")).strip().lower()
        if do_servo == 'y':
            await calibrate_servos(client)

        # Build Performance Events
        events = build_events(raw, home_key)
        rels = [e[1] for e in events]
        print(f"\nPerformance Events: {len(events)}, rel_idx range [{min(rels)}, {max(rels)}]")
        if min(rels) < 0:
            print("  [WARN] There are keys to the right of Home (rel_idx<0). Recommend setting Home further right.")

        input_ = (await ainput("\nStart Performance? [Enter=Start, q=Quit]: ")).strip().lower()
        if input_ == 'q':
            return

        while True:
            await perform(client, events, home_key)
            again = (await ainput("Play again? [y/n]: ")).strip().lower()
            if again != 'y':
                break

if __name__ == "__main__":
    asyncio.run(main())
