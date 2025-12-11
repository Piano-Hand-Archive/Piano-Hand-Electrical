from machine import Pin, PWM
import time, bluetooth

# ===== BLE UUIDs =====
SERVICE_UUID = bluetooth.UUID("19b10000-e8f2-537e-4f6c-d104768a1214")
CHAR_UUID    = bluetooth.UUID("19b10002-e8f2-537e-4f6c-d104768a1214")

# ===== Servo Setup =====
SERVO_PIN = 25           # change if needed
SERVO_MIN = 500          # 0 degrees
SERVO_MAX = 2500         # 180 degrees
SERVO_FREQ = 50

servo = PWM(Pin(SERVO_PIN), freq=SERVO_FREQ)

def servo_pulse(us):
    duty = int(us / 20000 * 1023)
    servo.duty(duty)

def servo_angle(deg):
    if deg < 0: deg = 0
    if deg > 180: deg = 180
    pulse = SERVO_MIN + (SERVO_MAX - SERVO_MIN) * (deg / 180)
    servo_pulse(int(pulse))
    print("Servo at:", deg, "degrees")

def servo_90_sweep():
    print("Sweep: 0° → 90° → 0°")
    servo_angle(0)
    time.sleep_ms(500)
    servo_angle(90)
    time.sleep_ms(500)
    servo_angle(0)
    time.sleep_ms(500)
    print("Done.")

# ===== BLE Setup =====
ble = bluetooth.BLE()
ble.active(True)

((CHAR_HANDLE,),) = ble.gatts_register_services((
    (SERVICE_UUID, ((CHAR_UUID, bluetooth.FLAG_WRITE),)),
))

def on_receive(data):
    try:
        message = data.decode().strip()
        print("RX:", message)
        if message.lower() == "servo":
            servo_90_sweep()
    except:
        pass

def ble_irq(event, data):
    if event == 3:  # Write event
        conn_handle, attr_handle = data
        if attr_handle == CHAR_HANDLE:
            on_receive(ble.gatts_read(CHAR_HANDLE))

def advertise():
    name = b"ESP32-Servo"
    adv = b"\x02\x01\x06" + bytes([len(name)+1, 0x09]) + name
    ble.gap_advertise(100_000, adv_data=adv)
    print("Advertising as ESP32-Servo")

ble.irq(ble_irq)
advertise()

while True:
    time.sleep_ms(200)
