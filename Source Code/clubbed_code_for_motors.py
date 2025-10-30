#incomplete (work in progress)

from machine import Pin, PWM, ADC
from time import sleep

def setup_servos(pins):
    servos = []
    for pin in pins
    pwm = PWM(Pin(pin)) #this is for analog output on a digital pin, theres documentation on it online
    pwm.freq(50)  # standard servo frequency
        servos.append(pwm)
    return servos

servo_pins = {
    "left": setup_servos([13,14,15,16,17,18,19,20,21,22]),
    "right": setup_servos([23,24,25,26,27,28,29,30,31,32])
}


def set_angle(servo, angle):
    duty = int(1638 + (angle / 180) * (8192 - 1638))  # 0°→1638, 180°→8192
    servo.duty_u16(duty)
    

#---------------------------------------------------
#encoder
encoder_pins = {
    "left": ADC(Pin(26)),   
    "right": ADC(Pin(27))
}


def read_hand_position(hand):
    # normalized float 0.0 → 1.0
    return encoder_pins[hand].read_u16() / 65535

def move_stepper_to(hand, target_float):
    min_steps, max_steps = 0, 200  # tune for your robot
    target_steps = int(min_steps + target_float * (max_steps - min_steps))
    delta = target_steps - current_steps[hand]
    if delta != 0:
        step_motor(steppers[hand], delta)
        current_steps[hand] = target_steps

# -----------------------
# PARSE TEXT FILE
# -----------------------
def parse_text_file(filename):
    events = []
    with open(filename) as f:
        current = {}
        for line in f:
            line = line.strip()
            if not line:
                if current:
                    events.append(current)
                    current = {}
                continue
            key, value = line.split(":", 1)
            key, value = key.strip(), value.strip()
            if value.lower() in ["true", "false"]:
                current[key] = value.lower() == "true"
            elif value.replace('.', '', 1).isdigit():
                current[key] = float(value)
            else:
                current[key] = value
        if current:
            events.append(current)
    return events


# Main
# -----------------------
events = parse_text_file("music_data.txt")

for e in events:
    if e["type"] == "note":
        hand = e["hand"]

        

  # SERVO MOTOR
        finger = int(e["finger"]) - 1
        angle = 60 if e["sharp"] else 120
        duration = float(e["duration"])

        set_angle(servo_pins[hand][finger], angle)
        sleep(duration)
        set_angle(servo_pins[hand][finger], 90)  # reset to neutral


