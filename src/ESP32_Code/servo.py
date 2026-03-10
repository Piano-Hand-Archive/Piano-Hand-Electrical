from machine import Pin, PWM
import time

# --- Hardware Pins ---
SERVO_PINS = [14, 25, 26]

# --- Servo Constants ---
MIN_US = 500
MAX_US = 2500
PERIOD_US = 20000 
MAX_ANGLE = 270.0

# --- Initialization ---
# Set up PWM for each pin at 50Hz (standard analog servo frequency)
print("Initializing PWM on pins:", SERVO_PINS)
fingers = [PWM(Pin(p), freq=50) for p in SERVO_PINS]

def set_angle(servo, angle):
    """Calculates duty cycle u16 for 270-degree servos"""
    # Constrain angle between 0 and 270 to prevent hardware glitches
    angle = max(0, min(MAX_ANGLE, angle))
    pulse = MIN_US + (angle / MAX_ANGLE) * (MAX_US - MIN_US)
    duty_u16 = int((pulse / PERIOD_US) * 65535)
    servo.duty_u16(duty_u16)

def run_servo_test():
    print("\n--- Starting Servo Test ---")
    
    # 1. Move all servos to the starting 'UP' position
    print("Moving all servos to 180 degrees (UP)...")
    for servo in fingers:
        set_angle(servo, 180)
    
    # Give them time to physically reach the starting position
    time.sleep(2) 
    
    # 2. Test each servo individually with a strike motion
    for i, servo in enumerate(fingers):
        print(f"\nTesting Servo {i+1} (Pin {SERVO_PINS[i]})...")
        
        print("  -> Striking down (0 deg)")
        set_angle(servo, 0)
        time.sleep(0.6) # Wait for physical swing
        
        print("  -> Lifting up (180 deg)")
        set_angle(servo, 180)
        time.sleep(0.6) # Wait for physical lift
        
    print("\n--- Servo test complete! ---")

# Execute the test
try:
    run_servo_test()
except KeyboardInterrupt:
    print("Test stopped by user.")
finally:
    # Optional: Deinitialize PWM to stop sending signals when the script ends
    for servo in fingers:
        servo.deinit()