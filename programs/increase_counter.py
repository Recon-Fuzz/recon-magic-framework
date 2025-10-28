"""
Simple counter script that increments a value stored in Counter.MD
"""

import os

COUNTER_FILE = "Counter.MD"

def increase_counter():
    """
    Read counter from Counter.MD, increment by 1, and write back.
    Creates the file with value 0 if it doesn't exist.
    """
    # Check if file exists
    if not os.path.exists(COUNTER_FILE):
        # Create file with initial value 0
        counter = 0
        print(f"Creating {COUNTER_FILE} with initial value: {counter}")
    else:
        # Read current value
        with open(COUNTER_FILE, 'r') as f:
            content = f.read().strip()
            try:
                counter = int(content)
            except ValueError:
                print(f"Warning: Invalid counter value '{content}', resetting to 0")
                counter = 0

        # Increment counter
        counter += 1
        print(f"Counter increased to: {counter}")

    # Write new value back to file
    with open(COUNTER_FILE, 'w') as f:
        f.write(str(counter))

    return counter

if __name__ == "__main__":
    increase_counter()
