#flashed on the esp32 firmware
import bluetooth
from machine import Pin, PWM
import time

# --- Servo Setup ---
servo_pin = Pin(13)
servo = PWM(servo_pin, freq=50)  # Standard 50 Hz

def set_angle(angle, step_delay=0.01):
    """Smoothly move servo to target angle"""
    current_duty = servo.duty()
    # Convert current duty to approximate angle
    current_angle = (current_duty / 1023 * 20000 - 500) / 11.111
    if current_angle < 0: current_angle = 0
    if current_angle > 180: current_angle = 180
    
    # Determine direction
    step = 1 if angle > current_angle else -1
    for a in range(int(current_angle), int(angle)+step, step):
        us = 500 + (a / 180) * 2000
        duty = int((us / 20000) * 1023)
        servo.duty(duty)
        time.sleep(step_delay)

def rotate_and_return(angle, cycles=1, step_delay=0.01):
    """Rotate to angle and back to 0, optionally multiple cycles"""
    for _ in range(cycles):
        set_angle(angle, step_delay)
        time.sleep(0.2)  # Hold at peak angle
        set_angle(0, step_delay)
        time.sleep(0.2)  # Hold at 0°

# --- BLE Setup ---
SERVICE_UUID = bluetooth.UUID("19b10000-e8f2-537e-4f6c-d104768a1214")
CHAR_UUID = bluetooth.UUID("19b10002-e8f2-537e-4f6c-d104768a1214")

ble = bluetooth.BLE()
ble.active(True)

def on_rx(value):
    try:
        cmd = value.decode().strip()
        print("Received:", cmd)
        if cmd.startswith("(") and cmd.endswith(")"):
            angle = int(cmd[1:-1])
            # Perform one rotation-and-back cycle
            rotate_and_return(angle)
    except Exception as e:
        print("Error:", e)

def ble_irq(event, data):
    if event == 1:
        print("Central connected")
    elif event == 2:
        print("Central disconnected")
        advertise()
    elif event == 3:
        conn_handle, attr_handle = data
        value = ble.gatts_read(attr_handle)
        on_rx(value)

def advertise():
    name = b'\x09ESP32-BLE-Control'
    adv_payload = b'\x02\x01\x06' + bytes([len(name)]) + name
    ble.gap_advertise(100, adv_data=adv_payload)
    print("Advertising as ESP32-BLE-Control...")

# Register BLE service
service = (SERVICE_UUID, ((CHAR_UUID, bluetooth.FLAG_WRITE),))
((char_handle,), ) = ble.gatts_register_services((service,))
ble.irq(ble_irq)
advertise()

# --- Keep alive ---
print("ESP32 running. Waiting for BLE commands...")
while True:
    time.sleep(1)

