from machine import Pin, ADC, PWM
from time import sleep

# --- CONFIGURATION ---
FINGER_COUNT = 5
servo_pins = [13, 14, 15, 16, 17]         # GPIO pins for servos
sensor_pins = [32, 33, 34, 35, 36]        # ADC pins for finger sensors
servo_freq = 50                           # Standard servo frequency (Hz)

# --- INITIALIZATION ---
servos = [PWM(Pin(p), freq=servo_freq) for p in servo_pins]
sensors = [ADC(Pin(p)) for p in sensor_pins]

# Set ADC width & attenuation for ESP32
for s in sensors:
    s.width(ADC.WIDTH_10BIT)  # 0–1023
    s.atten(ADC.ATTN_11DB)    # full range ~3.3V

# --- HELPER FUNCTIONS ---
def angle_to_duty(angle):
    """Convert angle (0–180°) to PWM duty for servo (ESP32: 0–1023)."""
    min_duty = 26   # ~0.5 ms pulse
    max_duty = 128  # ~2.5 ms pulse
    return int(min_duty + (max_duty - min_duty) * angle / 180)

def move_finger(servo, target_angle):
    """Move a single servo motor to target_angle."""
    duty = angle_to_duty(target_angle)
    servo.duty(duty)

def move_fingers(target_angles):
    """Move all fingers based on a list of angles."""
    for i in range(FINGER_COUNT):
        move_finger(servos[i], target_angles[i])

def read_finger_angles():
    """Read sensor values and map them to servo angles."""
    angles = []
    for s in sensors:
        val = s.read()              # 0–1023
        angle = int(val / 1023 * 180)
        angles.append(angle)
    return angles

# --- MAIN LOOP ---
while True:
    finger_angles = read_finger_angles()
    move_fingers(finger_angles)
    print("Finger angles:", finger_angles)
    sleep(0.1)
