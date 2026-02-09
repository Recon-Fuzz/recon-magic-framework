#!/bin/bash

# Build the project first
forge build

# Check if a base command argument is provided
if [ -z "$1" ]; then
    echo "Usage: $0 <base_command>"
    exit 1
fi

base_command="$1"

declare -A pid_to_file

# Define an array to hold the PIDs of the background processes
pids=()
# Define an array to hold the output file names
output_files=()
# Define an array to hold the tail PIDs
tail_pids=()

# Create a temporary directory for logs
log_dir=$(mktemp -d)
echo "Log directory: $log_dir"

# Function to cleanup background processes and temporary directory
cleanup() {
    echo "Cleaning up..."
    for pid in "${pids[@]}"; do
        kill $pid 2>/dev/null
    done
    for pid in "${tail_pids[@]}"; do
        kill $pid 2>/dev/null
    done
}

# Function to save the output of the first completed process
save_output() {
    echo "Saving output..."
    file="${pid_to_file[$completed_pid]}"
    if [ -s "$file" ]; then
        echo "Saving output of $file"
        cat "$file" > "/tmp/finalHalmos.txt"
        cat "$file"
        echo "Finished output"

    else
        echo "File $file is empty or does not exist."
    fi
}

# Trap to cleanup on script exit
# These functions get called once we reach the end of the script
trap "cleanup; save_output" EXIT

# Start the processes in the background and capture their logs
# Note that we've set the threads to 2, not sure on the effect yet
$base_command --solver-command cvc5 --solver-threads 2  --solver-timeout-assertion 0 --solver-timeout-branching 0 > "$log_dir/cvc5_output.log" 2>&1 &
pids+=($!)
pid_to_file[$!]="$log_dir/cvc5_output.log"

$base_command --solver-command yices --solver-threads 2  --solver-timeout-assertion 0 --solver-timeout-branching 0 > "$log_dir/yices_output.log" 2>&1 &
pids+=($!)
pid_to_file[$!]="$log_dir/yices_output.log"

$base_command --solver-command bitwuzla --solver-threads 2  --solver-timeout-assertion 0 --solver-timeout-branching 0 > "$log_dir/bitwuzla_output.log" 2>&1 &
pids+=($!)
pid_to_file[$!]="$log_dir/bitwuzla_output.log"

$base_command --solver-command boolector --solver-threads 2  --solver-timeout-assertion 0 --solver-timeout-branching 0 > "$log_dir/boolector_output.log" 2>&1 &
pids+=($!)
pid_to_file[$!]="$log_dir/boolector_output.log"

$base_command --solver-command z3 --solver-threads 2  --solver-timeout-assertion 0 --solver-timeout-branching 0 > "$log_dir/z3_output.log" 2>&1 &
pids+=($!)
pid_to_file[$!]="$log_dir/z3_output.log"


# Wait for any process to complete
# wait -n is not working for this case
wait_for_first_completion() {
    while :; do
        for pid in "${pids[@]}"; do
            if ! kill -0 "$pid" 2>/dev/null; then
                completed_pid=$pid
                return
            fi
        done
        sleep 1
    done
}

# Wait for any process to complete
wait_for_first_completion

# Debugging: Print which process completed first
echo "Process ${completed_pid} completed, proceeding to clean up and save output."

# Cleanup will be called by the trap
exit 0
