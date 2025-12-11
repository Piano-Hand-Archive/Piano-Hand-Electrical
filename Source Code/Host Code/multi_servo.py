from machine import Pin, PWM
import time, bluetooth, ujson

# ===== BLE UUIDs =====
SERVICE_UUID = bluetooth.UUID("19b10000-e8f2-537e-4f6c-d104768a1214")
CHAR_UUID    = bluetooth.UUID("19b10002-e8f2-537e-4f6c-d104768a1214")

# ===== Servo Parameters =====
SERVO_MIN_US = 500
SERVO_MAX_US = 2500
SERVO_FREQ   = 50

# ===== Servo Map (ID → Pin) =====
SERVOS = {
    1: PWM(Pin(25), freq=SERVO_FREQ),
    2: PWM(Pin(26), freq=SERVO_FREQ),
}

def servo_write_us(pwm, us):
    duty = int(us / 20000 * 1023)
    pwm.duty(duty)

def servo_angle(pwm, deg):
    if deg < 0: deg = 0
    if deg > 180: deg = 180
    pulse = SERVO_MIN_US + (SERVO_MAX_US - SERVO_MIN_US) * (deg / 180)
    servo_write_us(pwm, int(pulse))

def sweep_servos(ids):
    print("Sweeping servos:", ids)

    # start all at 0°
    for sid in ids:
        servo_angle(SERVOS[sid], 0)
    time.sleep_ms(300)

    # all to 90°
    for sid in ids:
        servo_angle(SERVOS[sid], 90)
    time.sleep_ms(500)

    # all back to 0°
    for sid in ids:
        servo_angle(SERVOS[sid], 0)
    time.sleep_ms(300)

    print("Sweep complete.")

# ===== BLE Setup =====
ble = bluetooth.BLE()
ble.active(True)

((CHAR_HANDLE,),) = ble.gatts_register_services((
    (SERVICE_UUID, ((CHAR_UUID, bluetooth.FLAG_WRITE),)),
))

def on_receive(data):
    try:
        text = data.decode().strip()
        print("RX:", text)

        # Expecting "[1,2]" or "[2]" or similar
        ids = ujson.loads(text)

        if not isinstance(ids, list):
            print("Invalid format. Expected list.")
            return

        valid = [i for i in ids if i in SERVOS]
        if not valid:
            print("No valid servo IDs.")
            return

        sweep_servos(valid)

    except Exception as e:
        print("Parse error:", e)

def ble_irq(event, data):
    if event == 3:  # Write event
        conn_handle, attr_handle = data
        if attr_handle == CHAR_HANDLE:
            on_receive(ble.gatts_read(CHAR_HANDLE))

def advertise():
    name = b"ESP32-MultiServo"
    adv = b"\x02\x01\x06" + bytes([len(name)+1, 0x09]) + name
    ble.gap_advertise(100_000, adv_data=adv)
    print("Advertising as ESP32-MultiServo")

ble.irq(ble_irq)
advertise()

while True:
    time.sleep_ms(200)
