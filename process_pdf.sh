#!/bin/bash

# Default values
DEFAULT_CHUNK_SIZE=100 # Pages per chunk if not specified
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PYTHON_EXEC="python3" # Or just "python" if python3 isn't standard

# --- Function Definitions ---

usage() {
  echo "Usage: $0 -i <input_path> -o <output_dir> [-c <pages_per_chunk> | -n <num_chunks>] [-h]"
  echo "  -i <input_path>        : Path to the input PDF file or a directory containing PDF files (required)."
  echo "  -o <output_dir>        : Path to the directory where output Markdown file(s) will be saved (required)."
  echo "  -c <pages_per_chunk>   : Split PDF into chunks of this many pages (default: $DEFAULT_CHUNK_SIZE)."
  echo "                           Overrides -n if both are provided."
  echo "  -n <num_chunks>        : Split PDF into exactly this many chunks."
  echo "                           Used only if -c is not provided."
  echo "  -h                     : Display this help message."
  exit 1
}

cleanup() {
  echo "Cleaning up temporary directory: $TEMP_DIR"
  rm -rf "$TEMP_DIR"
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
    if [ ! -x "$script_path" ] && [[ "$script_path" != *.py ]]; then
         # Make shell scripts executable if they aren't (Python scripts don't need it)
         chmod +x "$script_path" || { echo "Error: Failed to make script '$script_name' executable."; exit 1; }
    fi
}


# --- Argument Parsing ---

INPUT_PATH=""
OUTPUT_DIR=""
PAGES_PER_CHUNK=""
NUM_CHUNKS=""

while getopts "i:o:c:n:h" opt; do
  case $opt in
    i) INPUT_PATH="$OPTARG" ;;
    o) OUTPUT_DIR="$OPTARG" ;;
    c) PAGES_PER_CHUNK="$OPTARG" ;;
    n) NUM_CHUNKS="$OPTARG" ;;
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

# Validate numeric arguments if provided
if [ -n "$PAGES_PER_CHUNK" ] && ! [[ "$PAGES_PER_CHUNK" =~ ^[1-9][0-9]*$ ]]; then
    echo "Error: Pages per chunk (-c) must be a positive integer."
    exit 1
fi
if [ -n "$NUM_CHUNKS" ] && ! [[ "$NUM_CHUNKS" =~ ^[1-9][0-9]*$ ]]; then
    echo "Error: Number of chunks (-n) must be a positive integer."
    exit 1
fi


# --- Dependency Checks ---

echo "Checking dependencies..."
check_dependency "$PYTHON_EXEC"
check_dependency "qpdf"
check_script "$SCRIPT_DIR/adobe_extract.py"
check_script "$SCRIPT_DIR/json_to_markdown.py"
echo "Dependencies check passed."

# --- Setup ---

# Create temporary directory
TEMP_DIR=$(mktemp -d -t pdf_process_XXXXXX)
if [ ! -d "$TEMP_DIR" ]; then
    echo "Error: Failed to create temporary directory."
    exit 1
fi
echo "Created temporary directory: $TEMP_DIR"

# Set trap for cleanup
trap cleanup EXIT

EXTRACTED_ZIPS_DIR="$TEMP_DIR/extracted_zips"
PDF_CHUNKS_DIR="$TEMP_DIR/pdf_chunks"
# --- Core Processing Function ---

process_single_pdf() {
    local input_pdf_file="$1"
    local output_md_file="$2"
    local chunk_size_param="$3"
    local num_chunks_param="$4"
    local temp_base_dir="$5"
    local pdf_basename=$(basename "$input_pdf_file")

    echo "--------------------------------------------------"
    echo "Processing: $pdf_basename"
    echo "--------------------------------------------------"

    # Create specific temp dirs for this PDF
    local pdf_temp_dir="$temp_base_dir/$pdf_basename.tmp"
    mkdir -p "$pdf_temp_dir"
    local extracted_zips_dir="$pdf_temp_dir/extracted_zips"
    local pdf_chunks_dir="$pdf_temp_dir/pdf_chunks"
    mkdir -p "$extracted_zips_dir"
    mkdir -p "$pdf_chunks_dir"

    # --- PDF Splitting ---
    echo "Getting total page count for $pdf_basename..."
    local total_pages
    total_pages=$(qpdf --show-npages "$input_pdf_file" 2>/dev/null)
    if [ $? -ne 0 ] || ! [[ "$total_pages" =~ ^[0-9]+$ ]]; then
        echo "Error: Failed to get page count from $pdf_basename using qpdf. Skipping."
        return 1 # Indicate failure
    fi
    echo "Total pages: $total_pages"

    # Determine splitting strategy for this PDF
    local chunk_size
    local actual_num_chunks
    if [ -n "$chunk_size_param" ]; then
        chunk_size=$chunk_size_param
        actual_num_chunks=$(( (total_pages + chunk_size - 1) / chunk_size ))
        echo "Splitting into chunks of $chunk_size pages (estimated $actual_num_chunks chunks)."
    elif [ -n "$num_chunks_param" ]; then
        actual_num_chunks=$num_chunks_param
        chunk_size=$(( (total_pages + actual_num_chunks - 1) / actual_num_chunks ))
        echo "Splitting into $actual_num_chunks chunks (estimated $chunk_size pages per chunk)."
    else
        chunk_size=$DEFAULT_CHUNK_SIZE
        actual_num_chunks=$(( (total_pages + chunk_size - 1) / chunk_size ))
        echo "Using default chunk size: $chunk_size pages (estimated $actual_num_chunks chunks)."
    fi

    if [ "$total_pages" -eq 0 ]; then
        echo "Warning: PDF '$pdf_basename' has 0 pages. Skipping splitting and extraction."
        # Create an empty markdown file? Or just skip? Let's skip for now.
        return 0 # Indicate success (of skipping)
    fi

    echo "Splitting PDF into chunks..."
    local current_page=1
    local chunk_count=0
    while [ $current_page -le $total_pages ]; do
        chunk_count=$((chunk_count + 1))
        local end_page=$((current_page + chunk_size - 1))
        if [ $end_page -gt $total_pages ]; then
            end_page=$total_pages
        fi

        local chunk_filename=$(printf "chunk_%03d.pdf" $chunk_count)
        local chunk_filepath="$pdf_chunks_dir/$chunk_filename"

        echo "  Creating $chunk_filename (pages $current_page-$end_page)..."
        qpdf "$input_pdf_file" --pages . "$current_page-$end_page" -- "$chunk_filepath"
        if [ $? -ne 0 ]; then
            echo "Error: qpdf failed to create chunk $chunk_filename for $pdf_basename. Skipping rest of this PDF."
            return 1 # Indicate failure
        fi

        current_page=$((end_page + 1))
    done
    echo "PDF splitting complete. $chunk_count chunks created in $pdf_chunks_dir."

    # --- Adobe Extraction ---
    echo "Extracting text from PDF chunks using Adobe API..."
    local chunk_files=("$pdf_chunks_dir"/chunk_*.pdf)
    local processed_count=0
    local failed_count=0

    for chunk_pdf in "${chunk_files[@]}"; do
        local chunk_name=$(basename "$chunk_pdf")
        echo "  Processing $chunk_name..."
        "$PYTHON_EXEC" "$SCRIPT_DIR/adobe_extract.py" "$chunk_pdf" --output_dir "$extracted_zips_dir"
        if [ $? -ne 0 ]; then
            echo "  Warning: Failed to extract text from $chunk_name for $pdf_basename. Check adobe_extract.py output/logs."
            failed_count=$((failed_count + 1))
        else
            processed_count=$((processed_count + 1))
        fi
    done

    if [ $processed_count -eq 0 ] && [ ${#chunk_files[@]} -gt 0 ]; then
        echo "Error: No PDF chunks were successfully processed by adobe_extract.py for $pdf_basename. Skipping Markdown conversion for this PDF."
        return 1 # Indicate failure
    elif [ ${#chunk_files[@]} -eq 0 ]; then
         echo "No chunks were generated (likely 0 pages), skipping extraction and conversion."
         return 0 # Not an error in this case
    fi
    echo "Adobe extraction complete for $pdf_basename. Successfully processed $processed_count chunks. Failed: $failed_count."

    # --- Markdown Conversion ---
    echo "Converting extracted JSON data to Markdown for $pdf_basename..."
    "$PYTHON_EXEC" "$SCRIPT_DIR/json_to_markdown.py" "$extracted_zips_dir" "$output_md_file"
    if [ $? -ne 0 ]; then
        echo "Error: Failed to convert extracted data to Markdown for $pdf_basename. Check json_to_markdown.py output/logs."
        return 1 # Indicate failure
    fi

    echo "Markdown conversion complete for $pdf_basename. Output saved to: $output_md_file"
    echo "--------------------------------------------------"
    return 0 # Indicate success
}


# --- Main Execution Logic ---

overall_success=true

if [ -d "$INPUT_PATH" ]; then
    # Input is a directory
    echo "Input path is a directory. Processing PDF files within..."
    shopt -s nullglob # Prevent loop from running if no matches
    pdf_files=("$INPUT_PATH"/*.pdf)
    shopt -u nullglob

    if [ ${#pdf_files[@]} -eq 0 ]; then
        echo "No PDF files found in directory: $INPUT_PATH"
        exit 0
    fi

    echo "Found ${#pdf_files[@]} PDF file(s)."

    for pdf_file in "${pdf_files[@]}"; do
        pdf_basename=$(basename "$pdf_file")
        md_filename="${pdf_basename%.*}.md"
        output_md_path="$OUTPUT_DIR/$md_filename"

        process_single_pdf "$pdf_file" "$output_md_path" "$PAGES_PER_CHUNK" "$NUM_CHUNKS" "$TEMP_DIR"
        if [ $? -ne 0 ]; then
            overall_success=false
            echo ">>> Encountered errors processing $pdf_basename. Continuing with next file..."
        fi
    done

elif [ -f "$INPUT_PATH" ]; then
    # Input is a single file
    echo "Input path is a single file."
    pdf_basename=$(basename "$INPUT_PATH")
    md_filename="${pdf_basename%.*}.md"
    output_md_path="$OUTPUT_DIR/$md_filename" # Place output in the specified directory

    process_single_pdf "$INPUT_PATH" "$output_md_path" "$PAGES_PER_CHUNK" "$NUM_CHUNKS" "$TEMP_DIR"
     if [ $? -ne 0 ]; then
        overall_success=false
        echo ">>> Encountered errors processing $pdf_basename."
    fi
else
    echo "Error: Input path '$INPUT_PATH' is not a valid file or directory."
    exit 1
fi


# --- Completion ---
# Cleanup is handled by the trap

echo "=================================================="
if $overall_success; then
    echo "All processing finished successfully."
    exit 0
else
    echo "Processing finished with one or more errors."
    exit 1
fi

# Removed the original main processing logic, now encapsulated in process_single_pdf function