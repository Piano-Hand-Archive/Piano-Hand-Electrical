from machine import Pin, PWM
from time import sleep

servo_pin = Pin(0)
servo = PWM(servo_pin)
servo.freq(50)

# Calibrate these if needed
min_duty = 1802   # ~0°
max_duty = 7864   # ~180°

def set_angle(angle):
    # Clamp angle between 0 and 180
    angle = max(0, min(180, angle))
    
    duty = int(min_duty + (angle / 180) * (max_duty - min_duty))
    servo.duty_u16(duty)
    print(f"Angle: {angle}°, Duty: {duty}")
    
 #86 is the sweet spot without spasm   
set_angle(86)
sleep(4)
set_angle(80)
sleep(4)
set_angle(100)
sleep(4)



'''try:
    while True:
        set_angle(0)
        sleep(4)


        set_angle(90)
        sleep(4)

except KeyboardInterrupt:
    print("Keyboard interrupt")
    servo.deinit()'''
