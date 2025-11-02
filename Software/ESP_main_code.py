import bluetooth
from ble_advertising import advertising_payload
from machine import Pin
import struct, time

# Initialize LED pins
led_pins = [Pin(21, Pin.OUT), Pin(22, Pin.OUT), Pin(23, Pin.OUT)]

# BLE Service and Characteristic UUIDs
SERVICE_UUID = bluetooth.UUID("19b10000-e8f2-537e-4f6c-d104768a1214")
CHAR_UUID = bluetooth.UUID("19b10002-e8f2-537e-4f6c-d104768a1214")

ble = bluetooth.BLE()
ble.active(True)

def on_rx(v):
    try:
        cmd = v.decode("utf-8").strip()
        print("Received:", cmd)

        if cmd.startswith("(") and cmd.endswith(")"):
            parts = cmd[1:-1].split(",")
            led_num = int(parts[0]) - 1
            state = parts[1].strip().upper()
            led_pins[led_num].value(1 if state == "ON" else 0)
            print(f"LED {led_num+1} → {state}")

    except Exception as e:
        print("Error:", e)

def ble_irq(event, data):
    if event == 1:  # Central connected
        print("Connected to central")
    elif event == 2:  # Central disconnected
        print("Disconnected")
        advertise()
    elif event == 3:  # Write event
        conn_handle, attr_handle = data
        value = ble.gatts_read(attr_handle)
        on_rx(value)

def advertise():
    name = b'\x09ESP32-BLE-Control'
    adv_payload = b'\x02\x01\x06' + bytes([len(name)]) + name
    ble.gap_advertise(100, adv_data=adv_payload)
    print("Advertising as ESP32-BLE-Control...")


service = (
    SERVICE_UUID,
    (
        (CHAR_UUID, bluetooth.FLAG_WRITE),
    ),
)

((char_handle,), ) = ble.gatts_register_services((service,))
ble.irq(ble_irq)
advertise()

