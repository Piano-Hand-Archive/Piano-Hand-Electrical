from machine import Pin, PWM
import time
import math
import bluetooth
from rotary_irq_esp import RotaryIRQ

# ==========================================
# 1. Configuration & Hardware Dimensions
# ==========================================
# --- Bluetooth UUID ---
SERVICE_UUID = bluetooth.UUID("19b10000-e8f2-537e-4f6c-d104768a1214")
CHAR_UUID    = bluetooth.UUID("19b10002-e8f2-537e-4f6c-d104768a1214")

# --- Hardware Pins ---
DIR_PIN_NUM  = 32
STEP_PIN_NUM = 33
ENC_CLK_PIN  = 12
ENC_DT_PIN   = 13

# FIXED: Removed Pins 1 and 3 (TX/RX) to prevent immediate serial crashes. !! IMPORTANT
SERVO_PINS   = [14, 15, 26, 27] 

# --- Physical Dimensions (INCHES) ---
WHEEL_DIAMETER_IN = 3.11
WHEEL_CIRCUMFERENCE_IN = math.pi * WHEEL_DIAMETER_IN

# Change this
INCHES_PER_NOTE = 0.415

# --- Motor & Encoder Math ---
ENCODER_PPR = 600.0  
PULSES_PER_INCH = ENCODER_PPR / WHEEL_CIRCUMFERENCE_IN
STEPS_PER_INCH = 200.0  

TOLERANCE_IN = 0.04    
STEP_DELAY_US = 300    

# --- Servo Constants ---
MIN_US = 500
MAX_US = 2500
PERIOD_US = 20000  

NOTES = ("C","C#","D","D#","E","F","F#","G","G#","A","A#","B")

# ==========================================
# 2. Hardware Initialization
# ==========================================
dir_pin  = Pin(DIR_PIN_NUM, Pin.OUT, value=0)
step_pin = Pin(STEP_PIN_NUM, Pin.OUT, value=0)

encoder = RotaryIRQ(pin_num_clk=ENC_CLK_PIN,
                    pin_num_dt=ENC_DT_PIN,
                    reverse=False,
                    range_mode=RotaryIRQ.RANGE_UNBOUNDED)

fingers = [PWM(Pin(p), freq=50) for p in SERVO_PINS]

job_pending = False
target_distance_in = 0.0
finger_to_play = 0

# ==========================================
# 3. Helper Functions
# ==========================================
def set_angle(servo, angle):
    """Calculates duty cycle u16 for 270-degree servos"""
    # Constrain angle between 0 and 270 to prevent hardware glitches
    angle = max(0, min(270, angle))
    pulse = MIN_US + (angle / 270.0) * (MAX_US - MIN_US)
    duty_u16 = int((pulse / PERIOD_US) * 65535)
    servo.duty_u16(duty_u16)

def parse_note(note_str):
    s = note_str.strip().upper().replace('♯', '#')
    i_digit = next((i for i, ch in enumerate(s) if ch.isdigit()), None)
    if i_digit is None: return -1
    note_part = s[:i_digit]
    octave = int(s[i_digit:])
    try:
        return (octave - 1) * 12 + NOTES.index(note_part)
    except ValueError:
        return -1

def get_current_in():
    return encoder.value() / PULSES_PER_INCH

def move_stepper_relative(dist_in):
    if abs(dist_in) < 0.005: return
        
    steps = int(abs(dist_in) * STEPS_PER_INCH)
    dir_pin.value(1 if dist_in > 0 else 0)

    for i in range(steps):
        step_pin.value(1)
        time.sleep_us(STEP_DELAY_US)
        step_pin.value(0)
        time.sleep_us(STEP_DELAY_US)
        
        # Prints every 10 steps so you can visually verify it's moving correctly
        if i % 10 == 0:
            print(f"Moving... Encoder: {get_current_in():.3f} in")

def play_finger(finger_idx):
    if finger_idx < 1 or finger_idx > 4:
        print("Invalid finger number!")
        return
        
    servo = fingers[finger_idx - 1]
    
    # Applied working test values (180 degree swing with 0.6s delay)
    set_angle(servo, 0)     # Strike down 
    time.sleep(0.6)         # Wait for full physical swing
    set_angle(servo, 180)   # Lift up 
    time.sleep(0.6)         # Wait for full physical lift
    print(f"Finger {finger_idx} played.")

# Initialize servos to UP (180 deg) at boot
print("Initializing servos...")
for f in fingers:
    set_angle(f, 180)
# Increased delay here based on the working test code to ensure they all reach the top before BLE starts
time.sleep(1.0) 

# ==========================================
# 4. BLE Communication Logic
# ==========================================
ble = bluetooth.BLE()
ble.active(True)

((CHAR_HANDLE,),) = ble.gatts_register_services(((SERVICE_UUID, ((CHAR_UUID, bluetooth.FLAG_WRITE),)),))

def on_rx(v: bytes):
    global job_pending, target_distance_in, finger_to_play
    try:
        cmd = v.decode("utf-8").strip()
        print(f"\nReceived Command: {cmd}")

        if cmd.startswith("(") and cmd.endswith(")"):
            parts = [p.strip() for p in cmd[1:-1].split(",")]
            if len(parts) == 3:
                s_idx = parse_note(parts[0])
                e_idx = parse_note(parts[1])
                f_num = int(parts[2])

                if s_idx == -1 or e_idx == -1:
                    print("Invalid Note Format.")
                    return
                
                note_diff = e_idx - s_idx
                target_distance_in = note_diff * INCHES_PER_NOTE
                finger_to_play = f_num
                job_pending = True
            else:
                print("Format Error. Use (C4,G4,2)")
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
# 5. Main Loop (Execution & Correction)
# ==========================================
print("System Ready. Waiting for commands...")

while True:
    if job_pending:
        initial_in = get_current_in()
        absolute_target_in = initial_in + target_distance_in
        
        print(f"Target is {absolute_target_in:.3f} in. Initiating primary move...")
        
        # 1. Primary Move
        move_stepper_relative(target_distance_in)
        
        # 2. Correction Loop (While Loop)
        time.sleep(0.5) # Allow physical momentum to settle completely after main move
        current_in = get_current_in()
        error_in = absolute_target_in - current_in
        
        attempt = 1
        while abs(error_in) > TOLERANCE_IN:
            print(f"Correction {attempt}: Target: {absolute_target_in:.3f} in | Current: {current_in:.3f} in | Error: {error_in:.3f} in")
            print("Out of tolerance, correcting...")
            
            # Move the difference
            move_stepper_relative(error_in)
            
            # Wait, read again, and recalculate error
            time.sleep(0.5) 
            current_in = get_current_in()
            error_in = absolute_target_in - current_in
            attempt += 1
            
        print(f"Position verified within tolerance! Final position: {current_in:.3f} in")

        # 3. Strike Key
        play_finger(finger_to_play)
        
        # Clear job
        job_pending = False

    else:
        time.sleep_ms(20) # Keep CPU load low while idle