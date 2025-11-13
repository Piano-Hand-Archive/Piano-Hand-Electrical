angle_rotated = 180
pins = [25, 26, 12, 13]
time = 1000
hand = 'right'
angle = 0

def parse_line(line):
    line = line.strip()
    if not line:
        return None

    # Split timestamp and data
    t, arr = line.split(":", 1)
    t = int(t)

    # Remove [ ]
    arr = arr.strip()
    arr = arr[1:-1]

    parts = arr.split(",")

    # Convert fields
    def fix(x):
        x = x.strip()
        if x == "NaN":
            return None
        if x.startswith("'") and x.endswith("'"):
            return x[1:-1]             # 'right' → right
        if x.isdigit():
            return int(x)
        return x                       # notes like E4, D4, C4

    fields = [fix(p) for p in parts]

    return {
        "time": t,
        "initial": fields[0],
        "final": fields[1],
        "finger": fields[2],
        "angle": fields[3],
        "hand": fields[4],
        "num": fields[5]
    }


def read_and_parse_file(filename):
    results = []
    with open(filename, "r") as f:
        for line in f:
            parsed = parse_line(line)
            if parsed:
                results.append(parsed)
    return results


# ---- RUN ----
parsed_data = read_and_parse_file("sample.txt")
print(parsed_data)

