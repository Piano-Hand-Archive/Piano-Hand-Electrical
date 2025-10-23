from machine import Pin, PWM
from time import sleep
import sys

# --- CONFIGURATION ---
FINGER_COUNT = 5
servo_pins = [13, 14, 15, 16, 17]
servo_freq = 50  # standard servo PWM frequency

# Stepper driver pins (A4988/DRV8825)
step_pin = Pin(18, Pin.OUT)
dir_pin = Pin(19, Pin.OUT)

# Rotary encoder pins
encoder_clk = Pin(25, Pin.IN)
encoder_dt = Pin(26, Pin.IN)

# Servo limits (tune per your servo)
MIN_DUTY = 26
MAX_DUTY = 128

# --- INITIALIZATION ---
servos = [PWM(Pin(p), freq=servo_freq) for p in servo_pins]
last_clk = encoder_clk.value()

# --- HELPER FUNCTIONS ---
def angle_to_duty(angle):
    return int(MIN_DUTY + (MAX_DUTY - MIN_DUTY) * angle / 180)

def move_finger(finger_idx, angle):
    servos[finger_idx].duty(angle_to_duty(angle))

def move_fingers_smooth(target_angles, steps=10, delay=0.02):
    """Smoothly interpolate all fingers to target_angles."""
    current_angles = [0]*FINGER_COUNT
    for i in range(FINGER_COUNT):
        current_angles[i] = 90  # assume starting at 90°, adjust if needed
    
    for step in range(1, steps+1):
        for i in range(FINGER_COUNT):
            delta = target_angles[i] - current_angles[i]
            angle = current_angles[i] + delta * step / steps
            move_finger(i, angle)
        sleep(delay)

def stepper_move(target_pos, current_pos):
    """Move stepper to absolute position."""
    steps = target_pos - current_pos
    dir_pin.value(1 if steps > 0 else 0)
    for _ in range(abs(steps)):
        step_pin.value(1)
        sleep(0.002)
        step_pin.value(0)
        sleep(0.002)
    return target_pos

def read_encoder():
    global last_clk
    curr_clk = encoder_clk.value()
    if curr_clk != last_clk:
        delta = 1 if encoder_dt.value() != curr_clk else -1
        last_clk = curr_clk
        return delta
    return 0

def parse_csv_line(line):
    """
    Parse CSV line: duration_ms,stepper_pos,finger_idx,sharp
    Example: "500,120,2,True"
    """
    parts = line.strip().split(',')
    if len(parts) != 4:
        return None
    duration = int(parts[0])
    stepper_pos = int(parts[1])
    finger_idx = int(parts[2])
    sharp = parts[3].strip().lower() == 'true'
    return duration, stepper_pos, finger_idx, sharp

# --- MAIN LOOP ---
current_stepper_pos = 0
starting_angles = [90]*FINGER_COUNT  # starting finger positions

print("Starting CSV playback...")

try:
    with open('movements.csv', 'r') as f:
        for line in f:
            parsed = parse_csv_line(line)
            if parsed:
                duration, stepper_target, finger_idx, sharp = parsed
                
                # Determine finger angles for this step
                finger_angles = starting_angles.copy()
                finger_angles[finger_idx] = 90 + 15 if sharp else 90
                
                # Move fingers smoothly
                move_fingers_smooth(finger_angles, steps=10, delay=duration/1000/10)
                starting_angles = finger_angles.copy()
                
                # Move stepper
                current_stepper_pos = stepper_move(stepper_target, current_stepper_pos)
                
                sleep(duration/1000)  # hold note duration
except OSError:
    print("Error: 'movements.csv' not found.")

# Monitor encoder continuously
while True:
    delta = read_encoder()
    if delta != 0:
        print("Encoder moved:", delta)
    sleep(0.02)
