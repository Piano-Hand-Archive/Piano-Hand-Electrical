import time
from machine import Pin
from rotary_irq_esp import RotaryIRQ


# --- Pin Definitions ---
CLK_PIN = 25   # GPIO25
DT_PIN = 26    # GPIO26
LED_PIN = 14   # GPIO14 (LED)


# --- Constants ---
STEPS_PER_REVOLUTION = 600   # Encoder steps per turn
TOLERANCE_ANGLE = 5.0        # Degrees tolerance
MAX_ITERATIONS = 5
MOVEMENT_WINDOW_MS = 4000    # 2 seconds


# --- Target Position ---
desired_position = 90.0


# --- Initialize LED ---
led = Pin(LED_PIN, Pin.OUT)


# --- Initialize Rotary Encoder (Library) ---
r = RotaryIRQ(
    pin_num_clk=CLK_PIN,
    pin_num_dt=DT_PIN,
    reverse=True,
    incr=1,
    range_mode=RotaryIRQ.RANGE_UNBOUNDED,
    pull_up=True,
    half_step=False,
)


# --- Helper: Shortest Circular Distance ---
def get_distance(target, current):

    diff = abs(target - current) % 360
    return min(diff, 360 - diff)


# --- Initial Encoder Value ---
val_old = r.value()


print(f"Program Start. Target: {desired_position}°")
print("-" * 40)


# ==========================================
# Main Loop
# ==========================================
for i in range(MAX_ITERATIONS):

    print(f"\nIteration {i+1} / {MAX_ITERATIONS}")

    # 1. LED ON → Start moving
    led.value(1)
    print(">>> LED ON: MOVE ENCODER NOW <<<")

    start_time = time.ticks_ms()


    # 2. Read encoder for 2 seconds
    while time.ticks_diff(time.ticks_ms(), start_time) < MOVEMENT_WINDOW_MS:

        val_new = r.value()

        if val_new != val_old:
            val_old = val_new

        time.sleep_ms(5)   # small debounce delay


    # 3. LED OFF → Stop
    led.value(0)
    print(">>> LED OFF: STOP MOVING <<<")


    # 4. Convert steps → degrees
    steps = val_old % STEPS_PER_REVOLUTION

    current_degrees = steps * (360 / STEPS_PER_REVOLUTION)


    # 5. Distance to target
    distance = get_distance(desired_position, current_degrees)


    # 6. Status
    print(f"  Current Position: {current_degrees:.2f}°")
    print(f"  Target Position:  {desired_position:.2f}°")
    print(f"  Distance:         {distance:.2f}°")


    # 7. Check success
    if distance <= TOLERANCE_ANGLE:

        print("\n*** SUCCESS: Target Reached! ***")
        break

    else:
        print("  Not close enough. Retrying...")


    time.sleep(2)


# ==========================================
# End
# ==========================================
led.value(0)

print("-" * 40)
print("Program Ended.")

