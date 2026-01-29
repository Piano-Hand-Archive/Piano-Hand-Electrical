from machine import Pin
import time

# --- Pin Definitions ---
CLK_PIN = 25   # GPIO25 connected to rotary encoder CLK
DT_PIN = 26    # GPIO26 connected to rotary encoder DT
LED_PIN = 15   # GPIO connected to LED

# --- Constants ---
STEPS_PER_REVOLUTION = 600  # Steps for 360 degrees
TOLERANCE_ANGLE = 5.0       # Acceptable error (+/- degrees)
MAX_ITERATIONS = 5          # Number of attempts (n)
MOVEMENT_WINDOW_MS = 2000   # Time allowed for movement (2 seconds)

# --- Variables ---
counter = 0
prev_CLK_state = 0
current_degrees = 0.0

# --- User Input: Target ---
desired_position = 90.0

# --- Initialize Pins ---
clk = Pin(CLK_PIN, Pin.IN, Pin.PULL_UP)
dt = Pin(DT_PIN, Pin.IN, Pin.PULL_UP)
led = Pin(LED_PIN, Pin.OUT)

# --- Helper: Shortest Circular Distance ---
def get_distance(target, current):
    # Calculate difference
    diff = abs(target - current) % 360
    # Return the shorter path (clockwise vs counter-clockwise)
    return min(diff, 360 - diff)

# Read initial state before loop
prev_CLK_state = clk.value()

print(f"Program Start. Target: {desired_position}°. Tolerance: {TOLERANCE_ANGLE}°")
print("-" * 40)

# ==========================================
# Main Loop (Runs n times)
# ==========================================
for i in range(MAX_ITERATIONS):
    print(f"\nIteration {i + 1} / {MAX_ITERATIONS}")
    
    # 1. Turn LED ON (Start Movement Window)
    led.value(1)
    print(">>> LED ON: MOVE ENCODER NOW <<<")
    
    # Record the start time for the window
    start_time = time.ticks_ms()
    
    # 2. Polling Loop (Runs for 2 seconds)
    # The code stays inside this 'while' loop to catch fast encoder pulses
    while time.ticks_diff(time.ticks_ms(), start_time) < MOVEMENT_WINDOW_MS:
        
        CLK_state = clk.value()

        if CLK_state != prev_CLK_state:
            if CLK_state == 1:
                # Determine direction based on DT pin
                if dt.value() == 1:
                    counter -= 1 # Counter-Clockwise
                else:
                    counter += 1 # Clockwise
            prev_CLK_state = CLK_state
            
            # Optional: Print updates sparingly if needed, but avoiding print 
            # inside a fast loop is better for accuracy.
            
    # 3. Turn LED OFF (Stop Movement Window)
    led.value(0)
    print(">>> LED OFF: STOP MOVING <<<")

    # 4. Calculate Position and Distance
    # Normalize counter to degrees
    current_degrees = (counter % STEPS_PER_REVOLUTION) * (360 / STEPS_PER_REVOLUTION)
    
    # Calculate absolute shortest distance
    distance = get_distance(desired_position, current_degrees)

    # 5. Testing Statements
    print(f"  Current Position: {current_degrees:.2f}°")
    print(f"  Target Position:  {desired_position}°")
    print(f"  Distance to go:   {distance:.2f}°")

    # 6. Check Success Condition
    if distance <= TOLERANCE_ANGLE:
        print("\n*** SUCCESS: Target Reached within Tolerance! ***")
        break
    else:
        print("  Result: Not close enough. Retrying...")
    
    # Optional: Short pause before next iteration starts
    time.sleep(1)

# ==========================================
# End of Program
# ==========================================
led.value(0) # Ensure LED is off
print("-" * 40)
print("Program Ended.")