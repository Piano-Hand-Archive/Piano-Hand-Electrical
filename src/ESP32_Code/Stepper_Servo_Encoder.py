from machine import Pin, PWM
import time
import math
import bluetooth
from rotary_irq_esp import RotaryIRQ

# ==========================================
# 1. Configuration & Hardware Dimensions
# ==========================================
SERVICE_UUID = bluetooth.UUID("19b10000-e8f2-537e-4f6c-d104768a1214")
CHAR_UUID    = bluetooth.UUID("19b10002-e8f2-537e-4f6c-d104768a1214")

DIR_PIN_NUM  = 32
STEP_PIN_NUM = 33
ENC_CLK_PIN  = 12
ENC_DT_PIN   = 13
SERVO_PINS   = [14, 25, 26, 27, 15] 

WHEEL_DIAMETER_IN = 3.11 # CHANGE

WHEEL_CIRCUMFERENCE_IN = math.pi * WHEEL_DIAMETER_IN
INCHES_PER_NOTE = 0.800

ENCODER_PPR = 600.0  
PULSES_PER_INCH = ENCODER_PPR / WHEEL_CIRCUMFERENCE_IN
STEPS_PER_INCH = 200.0  

TOLERANCE_IN = 0.04    
STEP_DELAY_US = 300    

MIN_US = 500
MAX_US = 2500
PERIOD_US = 20000  

NOTES = ("C","C#","D","D#","E","F","F#","G","G#","A","A#","B")

# --- Timing Constants (Seconds) ---
# Adjust these to fine-tune your physical hardware movements
TIME_SERVO_STRIKE = 0.7       # 1. Minimum time to wait for the servo to physically strike down
TIME_SERVO_LIFT = 0.7         # 2. Minimum time to wait for the servo to rotate/lift back up
TIME_CORRECTION_STALL = 0.75   # 3. Time to let physical momentum settle before reading the encoder

# ==========================================
# 2. Hardware Initialization
# ==========================================
dir_pin  = Pin(DIR_PIN_NUM, Pin.OUT, value=0)
step_pin = Pin(STEP_PIN_NUM, Pin.OUT, value=0)

encoder = RotaryIRQ(pin_num_clk=ENC_CLK_PIN, pin_num_dt=ENC_DT_PIN, reverse=False, range_mode=RotaryIRQ.RANGE_UNBOUNDED)
fingers = [PWM(Pin(p), freq=50) for p in SERVO_PINS]

job_pending = False
target_distance_in = 0.0
active_fingers = []
finger_offsets = [0, 0, 0, 0, 0]
max_duration = 0.0

# ==========================================
# 3. Helper Functions
# ==========================================
def set_angle(servo, angle):
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

def set_status(status_str):
    """Updates the BLE characteristic so the PC knows the current state"""
    ble.gatts_write(CHAR_HANDLE, status_str.encode('utf-8'))

print("Initializing servos...")
for f in fingers:
    set_angle(f, 180)
time.sleep(1.0) 

# ==========================================
# 4. BLE Communication Logic
# ==========================================
ble = bluetooth.BLE()
ble.active(True)

# Add FLAG_READ so the PC can poll the status
((CHAR_HANDLE,),) = ble.gatts_register_services(((SERVICE_UUID, ((CHAR_UUID, bluetooth.FLAG_WRITE | bluetooth.FLAG_READ),)),))

def on_rx(v: bytes):
    global job_pending, target_distance_in, active_fingers, finger_offsets, max_duration
    try:
        cmd = v.decode("utf-8").strip()
        
        if cmd in ["READY", "BUSY"]: return 
        
        print(f"\nReceived Command: {cmd}")
        set_status("BUSY") 
        
        move_part, play_part = cmd.split("|")
        
        # 1. Parse Move
        m_parts = move_part.split(",")
        s_idx = parse_note(m_parts[0])
        e_idx = parse_note(m_parts[1])
        finger_offsets = [int(x) for x in m_parts[2:7]]
        
        target_distance_in = (e_idx - s_idx) * INCHES_PER_NOTE
        
        # 2. Parse Play
        active_fingers = []
        max_duration = 0.0
        for chord_part in play_part.split(";"):
            f_num, dur = chord_part.split(",")
            active_fingers.append(int(f_num))
            max_duration = max(max_duration, float(dur)) 
            
        job_pending = True
        
    except Exception as e:
        print("RX Error:", e)
        set_status("READY") 

def ble_irq(event, data):
    if event == 1: 
        print("BLE Connected")
        set_status("READY")
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
set_status("READY")
advertise()

# ==========================================
# 5. Main Loop (Execution & Correction)
# ==========================================
print("System Ready. Waiting for commands...")

while True:
    if job_pending:
        # --- 1. Move Stepper ---
        initial_in = get_current_in()
        absolute_target_in = initial_in + target_distance_in
        move_stepper_relative(target_distance_in)
        
        # --- 2. Correction Loop ---
        time.sleep(TIME_CORRECTION_STALL) 
        current_in = get_current_in()
        error_in = absolute_target_in - current_in
        
        while abs(error_in) > TOLERANCE_IN:
            move_stepper_relative(error_in)
            time.sleep(TIME_CORRECTION_STALL) 
            current_in = get_current_in()
            error_in = absolute_target_in - current_in
            
        # --- 3. Strike Key(s) ---
        print(f"Striking fingers: {active_fingers}")
        for f_idx in active_fingers:
            if 1 <= f_idx <= 5:
                servo = fingers[f_idx - 1]
                offset = finger_offsets[f_idx - 1]
                
                # Base strike angle is 15. Flat (-15) pushes it to 0. Sharp (+15) raises it to 30.
                strike_angle = 15 + offset 
                set_angle(servo, strike_angle)
                
        # Wait for the longer duration: either the text file's note length, or the physical minimum strike time
        time.sleep(max(max_duration, TIME_SERVO_STRIKE))
        
        # --- 4. Lift Key(s) ---
        for f_idx in active_fingers:
            if 1 <= f_idx <= 5:
                servo = fingers[f_idx - 1]
                set_angle(servo, 180) 
                
        time.sleep(TIME_SERVO_LIFT) # Wait for physical lift clearance
        
        # --- 5. Clean up and signal PC ---
        job_pending = False
        set_status("READY")
        print("Ready for next command.")

    else:
        time.sleep_ms(20)
