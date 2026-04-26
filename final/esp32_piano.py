"""
ESP32 Piano Player - BLE Peripheral (v2)
- Home = rightmost key (highest note)
- step_degrees is SIGNED (direction embedded in sign)
- Float absolute-angle tracking (no cumulative drift)
"""
import bluetooth
from machine import UART, Pin, I2C
import time
from collections import deque

# ============================================================
# HARDWARE SETUP
# ============================================================
uart = UART(2, baudrate=115200, tx=Pin(32), rx=Pin(33))
ADDR = 0xE0
MSTEP = 16
PULSES_PER_REV = 3200
SPEED_GEAR = 80

class PCA9685:
    def __init__(self, i2c, addr=0x40):
        self.i2c = i2c
        self.addr = addr
        self.i2c.writeto_mem(self.addr, 0x00, b'\x00')
    def set_pwm_freq(self, freq):
        prescale = int(25000000.0 / (4096 * freq) - 1)
        old = self.i2c.readfrom_mem(self.addr, 0x00, 1)
        self.i2c.writeto_mem(self.addr, 0x00, bytes([(old[0] & 0x7F) | 0x10]))
        self.i2c.writeto_mem(self.addr, 0xFE, bytes([prescale]))
        self.i2c.writeto_mem(self.addr, 0x00, old)
        time.sleep_ms(5)
        self.i2c.writeto_mem(self.addr, 0x00, bytes([old[0] | 0xa1]))
    def set_pwm(self, ch, on, off):
        data = bytearray([on & 0xFF, on >> 8, off & 0xFF, off >> 8])
        self.i2c.writeto_mem(self.addr, 0x06 + 4 * ch, data)

i2c = I2C(0, scl=Pin(14), sda=Pin(13))
pca = PCA9685(i2c)
pca.set_pwm_freq(50)

SERVO_CH = [0, 1, 2, 3, 4]
OPEN_PWM  = [90, 90, 90, 90, 90]
CLOSE_PWM = [90, 90, 90, 90, 90]

# ============================================================
# STEPPER STATE
# ============================================================
step_degrees = 30.0   # SIGNED. Sign = rotation direction per +1 index step.
current_deg  = 0.0    # Absolute angle from home, float-accumulated.

def calc_crc(data):
    return sum(data) & 0xFF

def _send_move(degrees):
    if abs(degrees) < 0.01:
        return
    pulses = int(round(abs(degrees) / 360.0 * PULSES_PER_REV))
    if pulses == 0:
        return
    is_ccw = degrees < 0
    speed_byte = (0x80 | SPEED_GEAR) if is_ccw else SPEED_GEAR
    data = bytes([
        ADDR, 0xFD, speed_byte,
        (pulses >> 24) & 0xFF, (pulses >> 16) & 0xFF,
        (pulses >> 8)  & 0xFF, pulses & 0xFF
    ])
    pkt = data + bytes([calc_crc(data)])
    uart.write(pkt)
    time.sleep_ms(5)
    uart.read()
    rpm = SPEED_GEAR * 30000 / (MSTEP * 200)
    rotations = abs(degrees) / 360.0
    wait_ms = int((rotations / rpm) * 60000 * 1.3) + 50
    time.sleep_ms(wait_ms)

def jog(degrees):
    """Relative move that does NOT update current_deg (for homing)."""
    _send_move(degrees)

def goto_idx(key_idx):
    """Absolute move. current_deg accumulates ideal target, so rounding self-corrects."""
    global current_deg
    target_deg = key_idx * step_degrees
    delta = target_deg - current_deg
    _send_move(delta)
    current_deg = target_deg

def press_chord(fingers, duration_s):
    chs = []
    for f in fingers:
        if 1 <= f <= 5:
            ch = f - 1
            pca.set_pwm(SERVO_CH[ch], 0, CLOSE_PWM[ch])
            chs.append(ch)
    if chs:
        time.sleep_ms(int(duration_s * 1000))
        for ch in chs:
            pca.set_pwm(SERVO_CH[ch], 0, OPEN_PWM[ch])

# ============================================================
# COMMAND HANDLER
# ============================================================
def handle_command(cmd):
    global step_degrees, current_deg
    try:
        if cmd.startswith("CAL:JOG:"):
            jog(float(cmd[8:]))
            return "OK:JOG"
        elif cmd == "CAL:SET_HOME":
            current_deg = 0.0
            return "OK:HOME"
        elif cmd.startswith("CAL:SET_STEP:"):
            step_degrees = float(cmd[13:])
            return "OK:STEP=%.4f" % step_degrees
        elif cmd.startswith("CAL:GOTO:"):
            goto_idx(int(cmd[9:]))
            return "OK:GOTO"
        elif cmd.startswith("CAL:SET_SERVO:"):
            parts = cmd[14:].split(":")
            ch = int(parts[0])
            if 0 <= ch <= 4:
                OPEN_PWM[ch]  = int(parts[1])
                CLOSE_PWM[ch] = int(parts[2])
            return "OK:SERVO"
        elif cmd.startswith("CAL:TEST_SERVO:"):
            parts = cmd[15:].split(":")
            ch = int(parts[0])
            state = parts[1]
            if 0 <= ch <= 4:
                pwm = CLOSE_PWM[ch] if state == "CLOSE" else OPEN_PWM[ch]
                pca.set_pwm(SERVO_CH[ch], 0, pwm)
            return "OK:TEST"
        elif cmd.startswith("PLAY:"):
            body = cmd[5:]
            move_part, play_part = body.split("|", 1)
            idx = int(move_part)
            fingers_str, dur_str = play_part.split(";", 1)
            fingers = [int(x) for x in fingers_str.split(",") if x]
            duration = float(dur_str)
            goto_idx(idx)
            press_chord(fingers, duration)
            return "OK:PLAY"
        elif cmd == "STATUS":
            return "OK:POS=%.3f,STEP=%.4f" % (current_deg, step_degrees)
        else:
            return "ERR:UNKNOWN"
    except Exception as e:
        return "ERR:%s" % str(e)

# ============================================================
# BLE PERIPHERAL
# ============================================================
BLE_NAME = "ESP32-Piano"
SERVICE_UUID = bluetooth.UUID("19b10000-e8f2-537e-4f6c-d104768a1214")
RX_UUID      = bluetooth.UUID("19b10001-e8f2-537e-4f6c-d104768a1214")
TX_UUID      = bluetooth.UUID("19b10002-e8f2-537e-4f6c-d104768a1214")
SERVICES = (
    (SERVICE_UUID, (
        (RX_UUID, bluetooth.FLAG_WRITE),
        (TX_UUID, bluetooth.FLAG_READ | bluetooth.FLAG_NOTIFY),
    )),
)

class BLEPeripheral:
    def __init__(self):
        self.ble = bluetooth.BLE()
        self.ble.active(True)
        self.ble.irq(self.ble_irq)
        ((self.rx_handle, self.tx_handle,),) = self.ble.gatts_register_services(SERVICES)
        self.buffer = b""
        self.queue = deque((), 32)
        self.conn_handle = None
        self.advertise()
        self.set_status("READY")

    def set_status(self, status):
        self.ble.gatts_write(self.tx_handle, status.encode('utf-8'))
        if self.conn_handle is not None:
            try:
                self.ble.gatts_notify(self.conn_handle, self.tx_handle)
            except:
                pass

    def advertise(self):
        name = bytes(BLE_NAME, 'utf-8')
        adv_data = bytearray(b'\x02\x01\x06') + bytearray([len(name) + 1, 0x09]) + name
        self.ble.gap_advertise(100, adv_data)

    def ble_irq(self, event, data):
        if event == 1:
            self.conn_handle, _, _ = data
            self.set_status("READY")
        elif event == 2:
            self.conn_handle = None
            self.advertise()
        elif event == 3:
            _, attr_handle = data
            if attr_handle == self.rx_handle:
                chunk = self.ble.gatts_read(self.rx_handle)
                # MicroPython bytearray doesn't support slice deletion,
                # so we use a plain bytes buffer and rebuild it.
                self.buffer = self.buffer + bytes(chunk)
                while True:
                    idx = self.buffer.find(b'\n')
                    if idx < 0:
                        break
                    try:
                        msg = self.buffer[:idx].decode('utf-8').strip()
                    except:
                        msg = ""
                    self.buffer = self.buffer[idx+1:]
                    if msg:
                        self.queue.append(msg)

def main():
    ble = BLEPeripheral()
    for ch in range(5):
        pca.set_pwm(SERVO_CH[ch], 0, OPEN_PWM[ch])
    print("ESP32 Piano v2 ready. Home = rightmost key.")
    while True:
        if ble.queue:
            cmd = ble.queue.popleft()
            ble.set_status("BUSY")
            time.sleep_ms(30)
            resp = handle_command(cmd)
            print("[CMD]", cmd, "->", resp)
            ble.set_status("READY")
        time.sleep_ms(20)

main()


