from machine import Pin, PWM
import time, bluetooth, ujson

# ===== BLE UUIDs =====
SERVICE_UUID = bluetooth.UUID("19b10000-e8f2-537e-4f6c-d104768a1214")
CHAR_UUID    = bluetooth.UUID("19b10002-e8f2-537e-4f6c-d104768a1214")

# ===== Servo Parameters =====
SERVO_MIN_US = 500
SERVO_MAX_US = 2500
SERVO_FREQ   = 50
PERIOD_US    = 20000  # 50 Hz

# ===== Servo Setup (ID → PWM) =====
SERVOS = {}

def init_servos():
    SERVOS[1] = PWM(Pin(25), freq=SERVO_FREQ)
    SERVOS[2] = PWM(Pin(26), freq=SERVO_FREQ)

def servo_write_us(pwm, us):
    us = max(SERVO_MIN_US, min(SERVO_MAX_US, us))
    duty_u16 = int(us * 65535 / PERIOD_US)
    pwm.duty_u16(duty_u16)

def servo_angle(pwm, deg):
    deg = max(0, min(180, deg))
    pulse = SERVO_MIN_US + (SERVO_MAX_US - SERVO_MIN_US) * deg / 180
    servo_write_us(pwm, int(pulse))

def sweep_servos(ids):
    print("Sweeping servos:", ids)

    for sid in ids:
        servo_angle(SERVOS[sid], 0)
    time.sleep_ms(300)

    for sid in ids:
        servo_angle(SERVOS[sid], 90)
    time.sleep_ms(500)

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

        ids = ujson.loads(text)

        if not isinstance(ids, list):
            print("Invalid format: expected list")
            return

        valid = [i for i in ids if i in SERVOS]
        if not valid:
            print("No valid servo IDs")
            return

        sweep_servos(valid)

    except Exception as e:
        print("Parse error:", e)

def ble_irq(event, data):
    if event == bluetooth.IRQ_GATTS_WRITE:
        conn_handle, attr_handle = data
        if attr_handle == CHAR_HANDLE:
            on_receive(ble.gatts_read(CHAR_HANDLE))

def advertise():
    name = b"ESP32-MultiServo"
    adv = b"\x02\x01\x06" + bytes([len(name) + 1, 0x09]) + name
    ble.gap_advertise(100_000, adv_data=adv)
    print("Advertising as ESP32-MultiServo")

# ===== Main =====
init_servos()
ble.irq(ble_irq)
advertise()

while True:
    time.sleep_ms(200)
