"""
PC Conductor (v2) - BLE Central for ESP32 Piano Player

Calibration flow (user-driven):
  1) "현재 어느 건반?"  (rightmost候補, e.g. C5)
  2) JOG 각도 입력 → 로봇이 움직임
  3) "이동 후 어느 건반?"  (e.g. A4)
  → step_degrees 부호까지 자동 역산
  4) Home 확정 (가장 오른쪽 끝)
  5) 서보 OPEN/CLOSE PWM 5채널 캘리브레이션
  6) CSV로 연주 시작

CSV 해석:
  - 'key' = 스테퍼가 이동할 건반 음이름 (재민의 정의)
  - 'finger' = 누를 서보 번호 (1~5)
  - 'thumb_pos' 컬럼은 사용하지 않음
  - 같은 (timestamp, key)에 여러 finger가 있으면 동시 타건
"""
import asyncio
import time
import csv
from collections import OrderedDict
from bleak import BleakScanner, BleakClient

# ============================================================
# CONFIG
# ============================================================
DEVICE_NAME = "ESP32-Piano"
RX_UUID = "19b10001-e8f2-537e-4f6c-d104768a1214"
TX_UUID = "19b10002-e8f2-537e-4f6c-d104768a1214"

CSV_PATH = "fingering_plan.csv"
INCLUDE_LEFT_HAND = False   # True로 바꾸면 L 행도 오른손과 동일 처리
CHUNK_SIZE = 20

# ============================================================
# KEY NAME <-> INDEX
# ============================================================
# White-key indexing that matches the CSV's thumb_pos values.
# Verified: D4 -> 29, G4 -> 32, G2 -> 18, D5 -> 36
# Formula: idx = octave*7 + {C:0, D:1, E:2, F:3, G:4, A:5, B:6}
NOTE_OFFSET = {'C': 0, 'D': 1, 'E': 2, 'F': 3, 'G': 4, 'A': 5, 'B': 6}
NOTE_NAMES  = 'CDEFGAB'

def key_to_idx(name):
    name = name.strip().upper()
    if len(name) < 2 or name[0] not in NOTE_OFFSET:
        raise ValueError(f"잘못된 음이름: {name}")
    octave = int(name[1:])
    return octave * 7 + NOTE_OFFSET[name[0]]

def idx_to_key(idx):
    return f"{NOTE_NAMES[idx % 7]}{idx // 7}"

# ============================================================
# ASYNC INPUT HELPER
# ============================================================
async def ainput(prompt=""):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, input, prompt)

# ============================================================
# BLE TRANSPORT
# ============================================================
async def send_cmd(client, cmd, timeout_s=20.0):
    payload = (cmd + "\n").encode('utf-8')
    for i in range(0, len(payload), CHUNK_SIZE):
        await client.write_gatt_char(RX_UUID, payload[i:i+CHUNK_SIZE], response=True)
        await asyncio.sleep(0.02)
    # Wait for BUSY (up to 1s); if READY seen first, command was instant.
    busy_seen = False
    for _ in range(20):
        await asyncio.sleep(0.05)
        try:
            status = (await client.read_gatt_char(TX_UUID)).decode('utf-8', errors='ignore').strip()
        except Exception:
            continue
        if status == "BUSY":
            busy_seen = True
            break
        if status == "READY":
            return
    if busy_seen:
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            await asyncio.sleep(0.05)
            try:
                status = (await client.read_gatt_char(TX_UUID)).decode('utf-8', errors='ignore').strip()
            except Exception:
                continue
            if status == "READY":
                return
        print(f"  [WARN] timeout after: {cmd}")

# ============================================================
# CSV LOADING
# ============================================================
def load_csv(path, include_left=False):
    """Returns raw list [(t, key, finger)], min_key, max_key."""
    raw = []
    keys = set()
    with open(path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['hand'] == 'L' and not include_left:
                continue
            try:
                t = float(row['start_time'])
                k = row['key'].strip()
                f_ = int(row['finger'])
                _ = key_to_idx(k)  # validate
            except Exception:
                continue
            raw.append((t, k, f_))
            keys.add(k)
    raw.sort(key=lambda x: (x[0], key_to_idx(x[1]), x[2]))
    if keys:
        sorted_keys = sorted(keys, key=key_to_idx)
        return raw, sorted_keys[0], sorted_keys[-1]
    return raw, None, None

def build_events(raw, home_key):
    """(t, key, finger)*  ->  (t, rel_idx, [fingers], duration)*
    rel_idx = home_idx - key_idx. Positive = 홈에서 왼쪽(낮은 음) 방향.
    """
    home_idx = key_to_idx(home_key)
    groups = OrderedDict()
    for t, k, f_ in raw:
        rel = home_idx - key_to_idx(k)
        groups.setdefault((t, rel), []).append(f_)
    items = list(groups.items())
    out = []
    for i, ((t, rel), fingers) in enumerate(items):
        if i + 1 < len(items):
            dur = items[i+1][0][0] - t
            dur = max(0.2, min(dur, 1.0))
        else:
            dur = 0.5
        out.append((t, rel, fingers, dur))
    return out

# ============================================================
# CALIBRATION
# ============================================================
def hline(): print("-" * 64)
def header(s):
    print(); hline(); print(f"  {s}"); hline()

async def calibrate_stepper(client, suggested_home):
    """Interactive stepper calibration.
    Returns (home_key, signed_step_deg)."""
    header("STEP 1  홈 설정 (오른쪽 끝 건반)")
    print(f"  CSV에서 가장 오른쪽 건반은 '{suggested_home}' 입니다.")
    print(f"  로봇 손을 '{suggested_home}' 또는 그보다 더 오른쪽 건반에 위치시켜 주세요.")
    print("  JOG 명령으로 미세 조정 가능합니다.\n")

    home_key = None
    while True:
        s = (await ainput("현재 로봇 손이 놓인 건반 (예: C5): ")).strip()
        try:
            key_to_idx(s)
        except Exception as e:
            print(f"  {e}")
            continue
        while True:
            c = (await ainput(f"  '{s}' 를 홈으로 확정? [y=확정, j=JOG조정, n=다시입력]: ")).strip().lower()
            if c == 'y':
                home_key = s
                await send_cmd(client, "CAL:SET_HOME")
                print(f"  ✓ 홈 = {home_key}")
                break
            elif c == 'j':
                while True:
                    j = (await ainput("    JOG 각도 (숫자, 빈 입력=종료): ")).strip()
                    if not j:
                        break
                    try:
                        await send_cmd(client, f"CAL:JOG:{float(j)}")
                    except ValueError:
                        print("    숫자만")
                # JOG 후 현재 위치 다시 물어보기 위해 바깥 루프로
                break
            elif c == 'n':
                break
            else:
                print("  y / j / n")
        if home_key is not None:
            break

    # ---------------------------------
    header("STEP 2  step_degrees 측정")
    print("  로봇을 JOG로 이동시키고, 이동 후 도달한 건반을 입력하면")
    print("  step_degrees 와 회전 방향(부호)이 자동으로 계산됩니다.\n")

    signed_step = None
    while True:
        while True:
            s = (await ainput("  JOG 각도 입력 (예: -60 또는 45): ")).strip()
            try:
                jog_deg = float(s)
                break
            except ValueError:
                print("  숫자만")
        await send_cmd(client, f"CAL:JOG:{jog_deg}")

        while True:
            new_name = (await ainput("  이동 후 도달한 건반 (예: A4): ")).strip()
            try:
                new_idx = key_to_idx(new_name)
                break
            except Exception as e:
                print(f"  {e}")

        home_idx = key_to_idx(home_key)
        diff = home_idx - new_idx   # +: new가 홈보다 낮은 음(왼쪽)
        if diff == 0:
            print("  같은 위치. 더 많이 움직여서 다시 측정하세요.")
            continue

        signed_step = jog_deg / diff
        print(f"  → {abs(jog_deg):.2f}도 이동, 건반 {abs(diff)}칸 차이")
        print(f"  → step_degrees = {signed_step:+.4f}  (인덱스 +1 당 회전 각도)")
        await send_cmd(client, f"CAL:SET_STEP:{signed_step:.6f}")

        # Restore physical position to home by reverse JOG
        # (current_deg 는 ESP32에서 여전히 0 이고, 물리도 홈이 되어야 싱크)
        print("  → 홈으로 물리 복귀...")
        await send_cmd(client, f"CAL:JOG:{-jog_deg}")

        c = (await ainput("  재측정? [y=재시도, Enter=확정]: ")).strip().lower()
        if c != 'y':
            break

    # ---------------------------------
    header("STEP 3  캘리브레이션 검증")
    print("  임의의 건반으로 이동 테스트. Enter만 눌러 건너뛸 수 있습니다.\n")
    while True:
        s = (await ainput("  이동 테스트할 건반 (예: A4, Enter=종료): ")).strip()
        if not s:
            break
        try:
            tgt_idx = key_to_idx(s)
        except Exception:
            print("  잘못된 형식")
            continue
        rel = key_to_idx(home_key) - tgt_idx
        await send_cmd(client, f"CAL:GOTO:{rel}")
        actual = (await ainput(f"    실제 도달 건반 (예상 {s}, Enter=OK): ")).strip()
        if actual and actual != s:
            try:
                actual_rel = key_to_idx(home_key) - key_to_idx(actual)
                if actual_rel != 0:
                    new_step = signed_step * (rel / actual_rel)
                    print(f"    재튜닝 step_degrees = {new_step:+.4f}")
                    signed_step = new_step
                    await send_cmd(client, f"CAL:SET_STEP:{signed_step:.6f}")
            except Exception:
                pass
        # 홈 복귀
        await send_cmd(client, "CAL:GOTO:0")

    print(f"\n  최종: 홈={home_key}, step_degrees={signed_step:+.4f}")
    return home_key, signed_step

async def calibrate_servos(client):
    header("STEP 4  서보 PWM 캘리브레이션 (채널 0~4)")
    print("  각 손가락별로 OPEN(뗌) / CLOSE(누름) PWM 값을 조정합니다.")
    print("  표준값: OPEN≈205 (1.0ms), CLOSE≈410 (2.0ms)")
    print("  현재 기본값 150/500 은 극단적이라 서보가 안 움직일 수 있으니 조정 권장.\n")

    for ch in range(5):
        print(f"-- 채널 {ch} (손가락 {ch+1}) --")
        opw, cpw = 150, 500
        while True:
            await send_cmd(client, f"CAL:SET_SERVO:{ch}:{opw}:{cpw}")
            await send_cmd(client, f"CAL:TEST_SERVO:{ch}:OPEN")
            s = (await ainput(f"  OPEN PWM (현재 {opw}, 숫자=변경, Enter=유지): ")).strip()
            if not s:
                break
            try:
                opw = int(s)
            except ValueError:
                print("  숫자만")
        while True:
            await send_cmd(client, f"CAL:SET_SERVO:{ch}:{opw}:{cpw}")
            await send_cmd(client, f"CAL:TEST_SERVO:{ch}:CLOSE")
            s = (await ainput(f"  CLOSE PWM (현재 {cpw}, 숫자=변경, Enter=유지): ")).strip()
            if not s:
                break
            try:
                cpw = int(s)
            except ValueError:
                print("  숫자만")
        await send_cmd(client, f"CAL:TEST_SERVO:{ch}:OPEN")
        print(f"  ✓ 채널 {ch}: OPEN={opw}, CLOSE={cpw}\n")

# ============================================================
# PERFORM
# ============================================================
async def perform(client, events, home_key):
    print(f"\n=== 연주 시작 — {len(events)} events, 홈={home_key} ===")
    start = time.time()
    skipped = 0
    for t, rel, fingers, dur in events:
        if rel < 0:
            skipped += 1
            continue
        target_abs = start + t
        now = time.time()
        if target_abs > now:
            await asyncio.sleep(target_abs - now)
        fstr = ','.join(str(f) for f in fingers)
        cmd = f"PLAY:{rel}|{fstr};{dur:.3f}"
        print(f"  [{t:6.2f}s] idx={rel:2d}  fingers={fstr}  dur={dur:.2f}")
        await send_cmd(client, cmd, timeout_s=10.0)
    if skipped:
        print(f"  [WARN] 홈보다 오른쪽(음수 idx) 이벤트 {skipped}개 스킵됨")
    print("=== 연주 완료 ===\n")

# ============================================================
# MAIN
# ============================================================
async def main():
    # CSV 먼저 읽어서 건반 범위 확인
    raw, min_key, max_key = load_csv(CSV_PATH, INCLUDE_LEFT_HAND)
    if not raw:
        print(f"{CSV_PATH} 가 비어있거나 읽을 수 없음.")
        return

    print("=" * 64)
    print("  ESP32 Piano Conductor v2")
    print("=" * 64)
    print(f"  CSV: {CSV_PATH}  ({len(raw)} 행)")
    print(f"  건반 범위: {min_key} (왼쪽/최저) ~ {max_key} (오른쪽/최고)")
    print(f"  홈(오른쪽 끝) 권장: {max_key} 이상")

    print(f"\n  BLE 스캔 중: {DEVICE_NAME}...")
    device = await BleakScanner.find_device_by_name(DEVICE_NAME)
    if not device:
        print(f"  {DEVICE_NAME} 못 찾음. 전원/광고 상태 확인.")
        return

    async with BleakClient(device) as client:
        print(f"  연결됨: {device.address}")
        await asyncio.sleep(0.5)

        # 스테퍼 캘리브레이션
        home_key, signed_step = await calibrate_stepper(client, max_key)

        # 서보 캘리브레이션
        do_servo = (await ainput("\n서보 캘리브레이션 진행? [y/n]: ")).strip().lower()
        if do_servo == 'y':
            await calibrate_servos(client)

        # 연주 이벤트 빌드
        events = build_events(raw, home_key)
        rels = [e[1] for e in events]
        print(f"\n연주 이벤트: {len(events)}, rel_idx 범위 [{min(rels)}, {max(rels)}]")
        if min(rels) < 0:
            print("  [WARN] 홈보다 오른쪽 건반(rel_idx<0)이 있음. 홈을 더 오른쪽으로 두는 걸 권장.")

        input_ = (await ainput("\n연주 시작? [Enter=시작, q=종료]: ")).strip().lower()
        if input_ == 'q':
            return

        while True:
            await perform(client, events, home_key)
            again = (await ainput("다시 연주? [y/n]: ")).strip().lower()
            if again != 'y':
                break

if __name__ == "__main__":
    asyncio.run(main())
