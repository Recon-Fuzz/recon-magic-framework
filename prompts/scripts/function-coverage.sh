#!/bin/bash

# Function Coverage Analysis Script
# This script extracts line coverage statistics for a specific function in a Solidity contract
# from an LCOV coverage file.
#
# Usage: ./function-coverage.sh <lcov_file> <contract_name> <function_name> [source_file]
#
# Arguments:
#   lcov_file      - Path to the LCOV file (e.g., echidna/coverage.1234567890.lcov)
#   contract_name  - Name of the contract (e.g., Morpho.sol)
#   function_name  - Name of the function to analyze (e.g., borrow)
#   source_file    - (Optional) Path to the source .sol file for line range detection
#
# Example:
#   ./function-coverage.sh echidna/coverage.1234567890.lcov Morpho.sol borrow src/Morpho.sol

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to display usage
usage() {
    echo "Usage: $0 <lcov_file> <contract_name> <function_name> [source_file]"
    echo ""
    echo "Arguments:"
    echo "  lcov_file      - Path to the LCOV file"
    echo "  contract_name  - Name of the contract (e.g., Morpho.sol)"
    echo "  function_name  - Name of the function to analyze"
    echo "  source_file    - (Optional) Path to the source .sol file"
    echo ""
    echo "Example:"
    echo "  $0 echidna/coverage.1234567890.lcov Morpho.sol borrow src/Morpho.sol"
    exit 1
}

# Check arguments
if [ $# -lt 3 ]; then
    usage
fi

LCOV_FILE="$1"
CONTRACT_NAME="$2"
FUNCTION_NAME="$3"
SOURCE_FILE="${4:-}"

# Validate lcov file exists
if [ ! -f "$LCOV_FILE" ]; then
    echo -e "${RED}Error: LCOV file not found: $LCOV_FILE${NC}"
    exit 1
fi

# Extract the contract section from the lcov file
echo -e "${BLUE}Analyzing coverage for function '${FUNCTION_NAME}' in ${CONTRACT_NAME}...${NC}"
echo ""

# Create a temporary file for the contract section
TEMP_CONTRACT=$(mktemp)
trap "rm -f $TEMP_CONTRACT" EXIT

# Extract the specific contract's coverage data
awk -v contract="$CONTRACT_NAME" '
    /^SF:/ {
        if ($0 ~ contract) {
            found=1;
            print;
        } else {
            found=0;
        }
    }
    found { print }
    /^end_of_record/ && found { exit }
' "$LCOV_FILE" > "$TEMP_CONTRACT"

# Check if contract was found
if [ ! -s "$TEMP_CONTRACT" ]; then
    echo -e "${RED}Error: Contract '$CONTRACT_NAME' not found in LCOV file${NC}"
    echo ""
    echo "Available contracts in LCOV file:"
    grep "^SF:" "$LCOV_FILE" | sed 's/^SF:/  /' | sort -u
    exit 1
fi

# Get the source file path from the lcov file
SOURCE_PATH=$(grep "^SF:" "$TEMP_CONTRACT" | head -1 | cut -d':' -f2-)

# Find the function definition and its start line
FUNCTION_START=$(grep "^FN:" "$TEMP_CONTRACT" | grep ",${FUNCTION_NAME}$" | cut -d':' -f2 | cut -d',' -f1)

if [ -z "$FUNCTION_START" ]; then
    echo -e "${RED}Error: Function '$FUNCTION_NAME' not found in $CONTRACT_NAME${NC}"
    echo ""
    echo "Available functions in $CONTRACT_NAME:"
    grep "^FN:" "$TEMP_CONTRACT" | cut -d':' -f2 | cut -d',' -f2 | sort -u | sed 's/^/  /'
    exit 1
fi

# Check if the function was called
FUNCTION_CALLED=$(grep "^FNDA:" "$TEMP_CONTRACT" | grep ",${FUNCTION_NAME}$" | cut -d':' -f2 | cut -d',' -f1)

echo -e "${BLUE}Function Details:${NC}"
echo "  Name: $FUNCTION_NAME"
echo "  Start Line: $FUNCTION_START"
echo "  Times Called: ${FUNCTION_CALLED:-0}"
echo ""

# Determine function end line
FUNCTION_END=""

# Try to find function end from source file if provided
if [ -n "$SOURCE_FILE" ] && [ -f "$SOURCE_FILE" ]; then
    # Find the function end by looking for the closing brace
    # This is a simplified approach - assumes proper indentation
    FUNCTION_END=$(awk -v start="$FUNCTION_START" '
        NR >= start {
            # Count braces to find matching closing brace
            for (i = 1; i <= length($0); i++) {
                char = substr($0, i, 1)
                if (char == "{") brace_count++
                if (char == "}") brace_count--
                if (brace_count == 0 && NR > start) {
                    print NR
                    exit
                }
            }
        }
    ' "$SOURCE_FILE")
elif [ -f "$SOURCE_PATH" ]; then
    # Try using the source path from lcov file
    FUNCTION_END=$(awk -v start="$FUNCTION_START" '
        NR >= start {
            for (i = 1; i <= length($0); i++) {
                char = substr($0, i, 1)
                if (char == "{") brace_count++
                if (char == "}") brace_count--
                if (brace_count == 0 && NR > start) {
                    print NR
                    exit
                }
            }
        }
    ' "$SOURCE_PATH")
fi

# If we couldn't determine the end, use the next function or end of file
if [ -z "$FUNCTION_END" ]; then
    # Find the next function start line
    NEXT_FUNCTION=$(grep "^FN:" "$TEMP_CONTRACT" | cut -d':' -f2 | cut -d',' -f1 | awk -v start="$FUNCTION_START" '$1 > start {print $1; exit}')

    if [ -n "$NEXT_FUNCTION" ]; then
        FUNCTION_END=$((NEXT_FUNCTION - 1))
        echo -e "${YELLOW}Warning: Function end estimated using next function start${NC}"
    else
        # Use the last line with coverage data
        FUNCTION_END=$(grep "^DA:" "$TEMP_CONTRACT" | cut -d':' -f2 | cut -d',' -f1 | sort -n | tail -1)
        echo -e "${YELLOW}Warning: Function end estimated using last coverage line${NC}"
    fi
fi

echo "  End Line: ${FUNCTION_END:-unknown}"
echo ""

# Extract line coverage data for the function's line range
echo -e "${BLUE}Line Coverage Analysis:${NC}"

if [ -n "$FUNCTION_END" ]; then
    # Extract DA lines within the function range
    COVERAGE_DATA=$(awk -v start="$FUNCTION_START" -v end="$FUNCTION_END" '
        /^DA:/ {
            line_num = substr($0, 4)
            split(line_num, parts, ",")
            num = parts[1]
            hits = parts[2]
            if (num >= start && num <= end) {
                print num "," hits
            }
        }
    ' "$TEMP_CONTRACT")

    if [ -z "$COVERAGE_DATA" ]; then
        echo -e "${YELLOW}No line coverage data found for this function${NC}"
        exit 0
    fi

    # Calculate coverage statistics
    TOTAL_LINES=0
    COVERED_LINES=0

    while IFS=',' read -r line_num hits; do
        TOTAL_LINES=$((TOTAL_LINES + 1))
        if [ "$hits" -gt 0 ]; then
            COVERED_LINES=$((COVERED_LINES + 1))
        fi
    done <<< "$COVERAGE_DATA"

    # Calculate percentage
    if [ $TOTAL_LINES -gt 0 ]; then
        PERCENTAGE=$(awk "BEGIN {printf \"%.2f\", ($COVERED_LINES / $TOTAL_LINES) * 100}")
    else
        PERCENTAGE="0.00"
    fi

    # Display summary
    echo -e "  Total Lines: $TOTAL_LINES"
    echo -e "  Covered Lines: $COVERED_LINES"
    echo -e "  Uncovered Lines: $((TOTAL_LINES - COVERED_LINES))"

    # Color code the percentage based on coverage
    if (( $(echo "$PERCENTAGE >= 80" | bc -l) )); then
        COLOR=$GREEN
    elif (( $(echo "$PERCENTAGE >= 50" | bc -l) )); then
        COLOR=$YELLOW
    else
        COLOR=$RED
    fi

    echo -e "  Coverage: ${COLOR}${PERCENTAGE}%${NC}"
    echo ""

    # Show detailed line-by-line coverage
    echo -e "${BLUE}Detailed Line Coverage:${NC}"
    echo "  Line | Hits | Status"
    echo "  -----|------|--------"

    while IFS=',' read -r line_num hits; do
        if [ "$hits" -gt 0 ]; then
            printf "  %-4s | %-4s | ${GREEN}✓ covered${NC}\n" "$line_num" "$hits"
        else
            printf "  %-4s | %-4s | ${RED}✗ not covered${NC}\n" "$line_num" "$hits"
        fi
    done <<< "$COVERAGE_DATA"

else
    echo -e "${RED}Could not determine function line range${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}Analysis complete!${NC}"
