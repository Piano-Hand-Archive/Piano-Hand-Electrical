import time


# Sample data parameters
angle_rotated = 180  # Rotation angle
pins = [25, 26, 12, 13]  # GPIO pins
hand = 'right'  # Which hand is being controlled
time_delay = 1  # Delay time for servo movement in seconds (previously 1000ms, now in seconds)
angle = 0  # Starting angle


# Function to parse individual lines of the file
def parse_line(line):
    line = line.strip()
    if not line:
        return None

    # Split timestamp and data
    t, arr = line.split(":", 1)
    t = int(t)

    # Remove [ ] around the list and split by commas
    arr = arr.strip()[1:-1]
    parts = arr.split(",")

    # Helper function to convert the fields into appropriate data types
    def fix(x):
        x = x.strip()
        if x == "NaN":
            return None
        if x.startswith("'") and x.endswith("'"):
            return x[1:-1]  # Remove quotes around strings like 'right' → right
        if x.isdigit():
            return int(x)
        return x  # Return notes (e.g., 'E4', 'D4', 'C4')

    # Parse and return the structured data
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


# Function to read the file and parse all lines
def read_and_parse_file(filename):
    results = []
    with open(filename, "r") as f:
        for line in f:
            parsed = parse_line(line)
            if parsed:
                results.append(parsed)
    return results


# Function to simulate servo movement (for testing)
def move_servo(finger, angle, hand, delay_time):
    # Example of a mapping from finger to servo pins based on the hand (right or left)
    # You would modify this mapping to reflect your actual setup
    finger_servo_map = {
        'right': {  # Right hand mapping
            1: [25, 26],  # Finger 1 corresponds to servos 25 and 26
            2: [12, 13],  # Finger 2 corresponds to servos 12 and 13
            # Add mappings for other fingers...
        },
        'left': {  # Left hand mapping
            1: [25, 26],
            2: [12, 13],
            # Add mappings for other fingers...
        }
    }

    # Get the servo pins for the finger and hand
    servos = finger_servo_map.get(hand, {}).get(finger, [])
    if not servos:
        print(f"Error: Finger {finger} not found for {hand} hand.")
        return

    print(f"Moving {finger} of {hand} hand to {angle} degrees using servos {servos}")
    # Implement actual servo movement here, e.g., using GPIO library
    # For now, we simulate by printing
    time.sleep(delay_time)  # Simulate the time delay for movement


# Function to process the parsed data
def process_data(parsed_data):
    last_time = time.time()

    for entry in parsed_data:
        t = entry["time"]
        initial = entry["initial"]
        final = entry["final"]
        finger = entry["finger"]
        angle = entry["angle"]
        hand = entry["hand"]
        num = entry["num"]

        # Handle multiple fingers
        if isinstance(finger, list):
            for f in finger:
                move_servo(f, angle, hand, time_delay)
        else:
            move_servo(finger, angle, hand, time_delay)

        # Simulate some time delay based on the provided time stamp
        print(f"Step completed for time {t} with initial {initial} and final {final}")
        time.sleep(1)  # Assuming each step has a delay of 1 second between them


# ---- RUN ----
filename = "sample.txt"  # Your input file name
parsed_data = read_and_parse_file(filename)
process_data(parsed_data)
