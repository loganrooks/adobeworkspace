#!/bin/bash

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PYTHON_EXEC="python3" # Or just "python" if python3 isn't standard
PYTHON_SCRIPT="$SCRIPT_DIR/epub_to_markdown.py"

# --- Function Definitions ---

usage() {
  echo "Usage: $0 -i <input_path> -o <output_dir> [-h]"
  echo "  -i <input_path> : Path to the input EPUB file or a directory containing EPUB files (required)."
  echo "  -o <output_dir> : Path to the directory where output Markdown file(s) will be saved (required)."
  echo "  -h              : Display this help message."
  exit 1
}

check_dependency() {
  if ! command -v "$1" &> /dev/null; then
    echo "Error: Required command '$1' not found. Please install it."
    exit 1
  fi
}

check_script() {
    local script_path="$1"
    local script_name=$(basename "$script_path")
    if [ ! -f "$script_path" ]; then
        echo "Error: Required script '$script_name' not found at '$script_path'."
        exit 1
    fi
}

# --- Argument Parsing ---

INPUT_PATH=""
OUTPUT_DIR=""

while getopts "i:o:h" opt; do
  case $opt in
    i) INPUT_PATH="$OPTARG" ;;
    o) OUTPUT_DIR="$OPTARG" ;;
    h) usage ;;
    \?) echo "Invalid option: -$OPTARG" >&2; usage ;;
  esac
done

# Validate required arguments
if [ -z "$INPUT_PATH" ] || [ -z "$OUTPUT_DIR" ]; then
  echo "Error: Input path (-i) and Output directory (-o) are required."
  usage
fi

# Validate input path existence
if [ ! -e "$INPUT_PATH" ]; then
  echo "Error: Input path not found: $INPUT_PATH"
  exit 1
fi

# Validate output directory
if [ -e "$OUTPUT_DIR" ] && [ ! -d "$OUTPUT_DIR" ]; then
    echo "Error: Output path '$OUTPUT_DIR' exists but is not a directory."
    exit 1
fi
# Create output directory if it doesn't exist
mkdir -p "$OUTPUT_DIR" || { echo "Error: Failed to create output directory '$OUTPUT_DIR'."; exit 1; }


# --- Dependency Checks ---
echo "Checking dependencies..."
check_dependency "$PYTHON_EXEC"
check_script "$PYTHON_SCRIPT"
echo "Dependencies check passed."

# --- Main Execution Logic ---

echo "Starting EPUB to Markdown conversion..."

# Call the Python script directly, as it handles both file and directory input
"$PYTHON_EXEC" "$PYTHON_SCRIPT" "$INPUT_PATH" "$OUTPUT_DIR"

exit_code=$?

if [ $exit_code -eq 0 ]; then
    echo "EPUB processing script finished successfully."
else
    echo "EPUB processing script finished with errors (Exit Code: $exit_code)."
fi

exit $exit_code