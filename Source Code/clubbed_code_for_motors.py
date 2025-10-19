from machine import Pin, PWM
from time import sleep
import sys

# --- CONFIGURATION ---
FINGER_COUNT = 5
servo_pins = [13, 14, 15, 16, 17]   # GPIO pins for servos
servo_freq = 50                     # I dont know the spec here so went with 50????

# Stepper driver pins (for A4988 / DRV8825)
step_pin = Pin(18, Pin.OUT)
dir_pin = Pin(19, Pin.OUT)

# Rotary encoder pins
encoder_clk = Pin(25, Pin.IN)
encoder_dt = Pin(26, Pin.IN)

# --- INITIALIZATION ---
servos = [PWM(Pin(p), freq=servo_freq) for p in servo_pins]

# --- HELPER FUNCTIONS ---
def angle_to_duty(angle):
    """Convert 0–180° to duty value (ESP32 0–1023)."""
    min_duty, max_duty = 26, 128
    return int(min_duty + (max_duty - min_duty) * angle / 180)

def move_finger(servo, angle):
    servo.duty(angle_to_duty(angle))

def move_fingers(target_angles):
    """Move all fingers to provided angle list."""
    for i in range(FINGER_COUNT):
        move_finger(servos[i], target_angles[i])

def stepper_rotate(direction, steps=1):
    """Rotate stepper a number of steps in a given direction."""
    dir_pin.value(1 if direction > 0 else 0)
    for _ in range(steps):
        step_pin.value(1)
        sleep(0.001)
        step_pin.value(0)
        sleep(0.001)

def read_encoder():
    """Return +1, -1, or 0 based on encoder movement."""
    global last_clk
    curr_clk = encoder_clk.value()
    if curr_clk != last_clk:
        if encoder_dt.value() != curr_clk:
            delta = 1
        else:
            delta = -1
        last_clk = curr_clk
        return delta
    return 0

# --- MAIN LOOP ---
last_clk = encoder_clk.value()

print("Ready. Send data in format: a1,a2,a3,a4,a5,stepper_dir,stepper_steps")

while True:
    if sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
        # Expected serial input format: "30,45,90,10,70,1,5"
        line = sys.stdin.readline().strip()
        try:
            data = [int(x) for x in line.split(',')]
            if len(data) == 7:
                finger_angles = data[:5]
                step_dir = data[5]
                step_steps = data[6]

                move_fingers(finger_angles)
                if step_steps > 0:
                    stepper_rotate(step_dir, step_steps)
                
                print("Updated:", finger_angles, "Stepper:", step_dir, step_steps)
        except:
            print("Invalid data")

    delta = read_encoder()
    if delta != 0:
        print("Encoder moved:", delta)

    sleep(0.02)
