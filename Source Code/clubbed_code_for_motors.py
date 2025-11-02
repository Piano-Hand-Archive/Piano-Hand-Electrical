#incomplete (work in progress)

'''SAMPLE COMMAND PROMPT
  {"hand":"left","finger":2,"angle":200,"duration":0.5},
  {"hand":"left","finger":2,"angle":90,"duration":0.5}
  
  we can also reset it to neutral by just commanding it to reset to neutral
  
  or exit for quit.
  
'''
import ujson as json
from machine import Pin, PWM
from time import sleep

# -----------------------
# Servo setup
# -----------------------
def setup_servos(pins):
    servos = []
    for pin in pins:
        pwm = PWM(Pin(pin))
        pwm.freq(50)  # 50 Hz typical servo PWM
        servos.append(pwm)
    return servos

servo_pins = {
    "left":  setup_servos([13,14,15,16,17,18,19,20,21,22]),
    "right": setup_servos([23,24,25,26,27,28,29,30,31,32])
}

#
# Servo control (270°)
# -----------------------
def set_angle(servo, angle):
    # Miuzie 270° servo expects roughly 500–2500 µs pulse width at 50 Hz
    # 0° → 500 µs, 270° → 2500 µs
    # Convert to 16-bit duty (0–65535) for MicroPython
    min_us, max_us = 500, 2500
    pulse = min_us + (angle / 270.0) * (max_us - min_us)
    duty_u16 = int((pulse / 20000) * 65535)  # 20 ms period → 50 Hz
    servo.duty_u16(duty_u16)

def neutral_all():
    for hand in servo_pins:
        for s in servo_pins[hand]:
            set_angle(s, 135)  # halfway for 270°
            
            

# -----------------------
# Core JSON Command
# -----------------------
def execute_json(cmd_json):
    try:
        data = json.loads(cmd_json)
    except Exception as e:
        print("Invalid JSON:", e)
        return

    # Single action
    if isinstance(data, dict):
        handle_action(data)
    # List of actions
    elif isinstance(data, list):
        for item in data:
            handle_action(item)
    else:
        print("Unsupported JSON format")

def handle_action(action):
    try:
        hand = action.get("hand", "right")
        finger = int(action.get("finger", 1)) - 1
        angle = float(action.get("angle", 135))
        duration = float(action.get("duration", 0.5))
        if hand not in servo_pins or finger >= len(servo_pins[hand]):
            print("Invalid hand/finger")
            return
        set_angle(servo_pins[hand][finger], angle)
        sleep(duration)
        if action.get("release", True):
            set_angle(servo_pins[hand][finger], action.get("release_angle", 135))
    except Exception as e:
        print("Error:", e)

# -----------------------
# Command prompt
# -----------------------
def repl():
    print("=== JSON Command Prompt Ready ===")
    print('Example: {"hand":"left","finger":1,"angle":200,"duration":1.0}')
    print("Type 'exit' to quit, 'neutral' to reset all.\n")
    while True:
        try:
            cmd = input("cmd> ").strip()
            if not cmd:
                continue
            if cmd == "exit":
                break
            elif cmd == "neutral":
                neutral_all()
            else:
                execute_json(cmd)
        except KeyboardInterrupt:
            break
        except Exception as e:
            print("REPL error:", e)

# -----------------------
# Run
# -----------------------
if __name__ == "__main__":
    neutral_all()
    repl()


