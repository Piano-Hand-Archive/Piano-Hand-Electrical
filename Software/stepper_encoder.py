from machine import Pin
import time
import bluetooth
from rotary_irq_esp import RotaryIRQ

# ==========================================
# 1. Configuration
# ==========================================
# --- Bluetooth UUID ---
SERVICE_UUID = bluetooth.UUID("19b10000-e8f2-537e-4f6c-d104768a1214")
CHAR_UUID    = bluetooth.UUID("19b10002-e8f2-537e-4f6c-d104768a1214")

# --- Pin Definitions ---
DIR_PIN_NUM  = 33
STEP_PIN_NUM = 32
CLK_PIN      = 25   # Encoder CLK
DT_PIN       = 26   # Encoder DT

# --- Constants ---
KEY_ANGLE_DEG  = 19.6   # Angle per key (degrees)
MAX_OCTAVE     = 5
PULSE_US       = 200   # Motor speed (larger = slower & more stable)
TOLERANCE_PCT  = 0.03   # Tolerance band 3% (0.03)

# --- Encoder Settings ---
STEPS_PER_REV_ENC = 600 # Encoder steps per revolution

NOTES = ("C","C#","D","D#","E","F","F#","G","G#","A","A#","B")

# ==========================================
# 2. Hardware Initialization
# ==========================================
dir_pin  = Pin(DIR_PIN_NUM, Pin.OUT, value=0)
step_pin = Pin(STEP_PIN_NUM, Pin.OUT, value=0)

# Initialize the encoder (if direction is reversed, change reverse=False)
r = RotaryIRQ(pin_num_clk=CLK_PIN,
              pin_num_dt=DT_PIN,
              reverse=True,
              incr=1,
              range_mode=RotaryIRQ.RANGE_UNBOUNDED,
              pull_up=True,
              half_step=False)

# Global variables
target_angle = 0.0      # Target angle (absolute)
is_active = False       # Whether motion is in progress

# ==========================================
# 3. Helper Functions
# ==========================================
def get_current_angle():
    # Convert encoder count to degrees
    return r.value() * (360 / STEPS_PER_REV_ENC)

def parse_note_with_octave(note_input):
    if not note_input: return -1
    s = note_input.strip().upper().replace('♯', '#')
    i_digit = None
    for i, ch in enumerate(s):
        if ch.isdigit():
            i_digit = i; break
    if i_digit is None or i_digit == 0: return -1

    note_part   = s[:i_digit]
    octave_part = s[i_digit:]
    try:
        note_index = NOTES.index(note_part)
        octave     = int(octave_part)
    except: return -1

    if octave < 1 or octave > MAX_OCTAVE: return -1
    return (octave - 1) * 12 + note_index

# ===========================================
# 4. BLE Communication Logic
# ==========================================
ble = bluetooth.BLE()
ble.active(True)

((CHAR_HANDLE,),) = ble.gatts_register_services((
    (SERVICE_UUID, ((CHAR_UUID, bluetooth.FLAG_WRITE),)),
))

def on_rx(v: bytes):
    global target_angle, is_active
    try:
        cmd = v.decode("utf-8").strip()
        print(f"Received Command: {cmd}")

        if cmd.startswith("(") and cmd.endswith(")"):
            parts = [p.strip() for p in cmd[1:-1].split(",")]
            if len(parts) != 2: return

            s_idx = parse_note_with_octave(parts[0])
            e_idx = parse_note_with_octave(parts[1])

            if s_idx == -1 or e_idx == -1:
                print("Invalid Note Format.")
                return

            # Compute relative angle to move
            diff_notes = e_idx - s_idx
            move_angle = diff_notes * KEY_ANGLE_DEG

            # Set absolute target angle based on current position
            current_ang = get_current_angle()
            target_angle = current_ang + move_angle

            print(f"Job: Move {move_angle:.2f}°")
            print(f"Current: {current_ang:.2f}° -> Target: {target_angle:.2f}°")

            is_active = True # Signal to start control loop

        else:
            print("Format Error. Use (C1,E2)")
    except Exception as e:
        print("RX Error:", e)

def ble_irq(event, data):
    if event == 1: print("BLE Connected")
    elif event == 2:
        print("BLE Disconnected")
        advertise()
    elif event == 3:
        conn_handle, attr_handle = data
        if attr_handle == CHAR_HANDLE:
            on_rx(ble.gatts_read(CHAR_HANDLE))

def advertise():
    name = b"ESP32-BLE-Control"
    adv  = b"\x02\x01\x06" + bytes((len(name)+1, 0x09)) + name
    ble.gap_advertise(100_000, adv_data=adv)
    print("Advertising...")

ble.irq(ble_irq)
advertise()

# ==========================================
# 5. Main Loop (Feedback Control)
# ==========================================
print("System Ready. Waiting for command...")

while True:
    if is_active:
        # 1. Measure current state
        current_deg = get_current_angle()
        error = target_angle - current_deg

        # 2. Compute tolerance (3% of target angle, or at least 1 degree)
        # Give at least 1 degree slack in case target is near 0.
        tolerance = max(abs(target_angle) * TOLERANCE_PCT, 1.0)

        # 3. Check if target is reached
        if abs(error) <= tolerance:
            print(f"Reached! Cur: {current_deg:.2f}° / Tgt: {target_angle:.2f}° (Err: {error:.2f}°)")
            is_active = False # Stop the motor

        else:
            # 4. Drive the motor (feedback)
            # If target is larger (error > 0), rotate CW (1), else CCW (0)
            # Depending on wiring, you may need to swap 1/0 or rewire.
            direction = 1 if error > 0 else 0

            dir_pin.value(direction)

            # Move 1 step
            step_pin.value(1)
            time.sleep_us(PULSE_US)
            step_pin.value(0)
            time.sleep_us(PULSE_US)

            # Debug (printing too often can slow down the loop; uncomment if needed)
            # print(f"Move.. Cur: {current_deg:.1f} Tgt: {target_angle:.1f}")

    else:
        # Idle state (reduce CPU usage)
        time.sleep_ms(20)


