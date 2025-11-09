from machine import Pin
import time
import bluetooth

SERVICE_UUID = bluetooth.UUID("19b10000-e8f2-537e-4f6c-d104768a1214")
CHAR_UUID    = bluetooth.UUID("19b10002-e8f2-537e-4f6c-d104768a1214")

DIR_PIN_NUM  = 33
STEP_PIN_NUM = 32
STEP_ANGLE_DEG = 1.8
KEY_ANGLE_DEG  = 19.6
MAX_OCTAVE     = 5
PULSE_US       = 1000

NOTES = ("C","C#","D","D#","E","F","F#","G","G#","A","A#","B")

dir_pin  = Pin(DIR_PIN_NUM, Pin.OUT, value=0)
step_pin = Pin(STEP_PIN_NUM, Pin.OUT, value=0)

def rotate_step(angle_deg, clockwise=True):
    steps = int(angle_deg / STEP_ANGLE_DEG + 0.5)
    dir_pin.value(1 if clockwise else 0)
    print(("Clockwise " if clockwise else "Counterclockwise ")
          + "{:.2f}° rotation ({} steps)".format(angle_deg, steps))
    for _ in range(steps):
        step_pin.value(1); time.sleep_us(PULSE_US)
        step_pin.value(0); time.sleep_us(PULSE_US)
    print("Rotation complete!")

def parse_note_with_octave(note_input):
    if not note_input:
        return -1
    s = note_input.strip().upper().replace('♯', '#')
    i_digit = None
    for i, ch in enumerate(s):
        if ch.isdigit():
            i_digit = i; break
    if i_digit is None or i_digit == 0:
        return -1
    note_part   = s[:i_digit]
    octave_part = s[i_digit:]
    try:
        note_index = NOTES.index(note_part)
        octave     = int(octave_part)
    except Exception:
        return -1
    if octave < 1 or octave > MAX_OCTAVE:
        return -1
    return (octave - 1) * 12 + note_index

ble = bluetooth.BLE()
ble.active(True)

((CHAR_HANDLE,),) = ble.gatts_register_services((
    (SERVICE_UUID, ((CHAR_UUID, bluetooth.FLAG_WRITE),)),
))

def on_rx(v: bytes):
    try:
        cmd = v.decode("utf-8").strip()
        print("Received:", cmd)
        if cmd.startswith("(") and cmd.endswith(")"):
            parts = [p.strip() for p in cmd[1:-1].split(",")]
            if len(parts) != 2:
                print("Use format: (C1,E3)")
                return
            cur = parts[0].upper()
            tgt = parts[1].upper()
            s_idx = parse_note_with_octave(cur)
            e_idx = parse_note_with_octave(tgt)
            if s_idx == -1 or e_idx == -1:
                print("⚠️ Invalid input. Use C1, D#2, F3 ... (1~5)")
                return
            diff = e_idx - s_idx
            if diff == 0:
                print("Same position → No rotation.")
                return
            angle = abs(diff) * KEY_ANGLE_DEG
            rotate_step(angle, clockwise=(diff > 0))
            print("Waiting for next command...\n")
        else:
            print("Invalid format. Try: (C1,E3)")
    except Exception as e:
        print("Error:", e)

def ble_irq(event, data):
    if event == 1:      
        print("Connected")
    elif event == 2:  
        print("Disconnected")
        advertise()
    elif event == 3:    
        conn_handle, attr_handle = data
        if attr_handle == CHAR_HANDLE:
            on_rx(ble.gatts_read(CHAR_HANDLE))

def advertise():
    name = b"ESP32-BLE-Control"
    adv  = b"\x02\x01\x06" + bytes((len(name)+1, 0x09)) + name
    ble.gap_advertise(100_000, adv_data=adv)  # 100 ms
    print("Advertising as ESP32-BLE-Control...")

ble.irq(ble_irq)
advertise()

# keep alive
while True:
    time.sleep_ms(200)

