import argparse
import json
import zipfile
import os
import re
from pathlib import Path

def natural_sort_key(s):
    """Helper function for natural sorting of filenames."""
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s)]

def json_to_markdown(input_dir, output_md_path):
    """
    Reads structuredData.json from ZIP files in input_dir, converts content
    to Markdown (excluding footnotes), and saves to output_md_path.

    Args:
        input_dir (str): Path to the directory containing ZIP files.
        output_md_path (str): Path to the output Markdown file.
    """
    input_path = Path(input_dir)
    output_path = Path(output_md_path)
    markdown_content = []

    # Find and sort zip files naturally
    zip_files = sorted(
        [f for f in input_path.glob('*.zip') if f.is_file()],
        key=lambda x: natural_sort_key(x.name)
    )

    if not zip_files:
        print(f"No ZIP files found in directory: {input_dir}")
        return

    print(f"Found {len(zip_files)} ZIP files to process.")

    for zip_filepath in zip_files:
        print(f"Processing {zip_filepath.name}...")
        try:
            with zipfile.ZipFile(zip_filepath, 'r') as archive:
                if 'structuredData.json' not in archive.namelist():
                    print(f"  Warning: structuredData.json not found in {zip_filepath.name}. Skipping.")
                    continue

                with archive.open('structuredData.json') as json_file:
                    try:
                        data = json.load(json_file)
                    except json.JSONDecodeError as e:
                        print(f"  Error decoding JSON in {zip_filepath.name}: {e}. Skipping.")
                        continue

                    chunk_content = []
                    for element in data.get("elements", []):
                        path = element.get("Path", "")
                        text = element.get("Text", "").strip()

                        # Skip footnotes and empty text elements
                        if "Footnote" in path or not text:
                            continue

                        # Basic Markdown conversion (can be expanded)
                        if "/H1" in path:
                            chunk_content.append(f"# {text}\n")
                        elif "/H2" in path:
                            chunk_content.append(f"## {text}\n")
                        elif "/H3" in path:
                            chunk_content.append(f"### {text}\n")
                        elif "/H4" in path:
                            chunk_content.append(f"#### {text}\n")
                        elif "/H5" in path:
                            chunk_content.append(f"##### {text}\n")
                        elif "/H6" in path:
                            chunk_content.append(f"###### {text}\n")
                        elif "/LBody" in path or "/LI" in path: # Handle list items
                             # Basic list handling - assumes simple lists for now
                             # More complex list structures might need refinement
                             indent_level = path.count('/L[') -1 # Crude indent approximation
                             indent = "  " * indent_level
                             chunk_content.append(f"{indent}* {text}")
                        elif "/P" in path: # Paragraphs
                            chunk_content.append(text)
                        # Add more element types (e.g., Tables) if needed

                    # Add a separator between chunks for clarity, maybe a horizontal rule
                    if chunk_content:
                         markdown_content.append("\n\n".join(chunk_content))
                         markdown_content.append("\n\n---\n\n") # Separator

        except zipfile.BadZipFile:
            print(f"  Error: Bad ZIP file {zip_filepath.name}. Skipping.")
        except Exception as e:
            print(f"  An unexpected error occurred processing {zip_filepath.name}: {e}")

    # Remove the last separator if added
    if markdown_content and markdown_content[-1].strip() == "---":
        markdown_content.pop()

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Write the combined content to the output Markdown file
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(markdown_content))

    print(f"\nMarkdown conversion complete. Output saved to: {output_md_path}")


def main():
    parser = argparse.ArgumentParser(description='Convert Adobe Extract API JSON outputs (in ZIPs) to a single Markdown file.')
    parser.add_argument('input_dir', help='Directory containing the ZIP files from adobe_extract.py')
    parser.add_argument('output_md', help='Path for the final output Markdown file')

    args = parser.parse_args()

    if not os.path.isdir(args.input_dir):
        print(f"Error: Input directory not found: {args.input_dir}")
        return

    json_to_markdown(args.input_dir, args.output_md)

if __name__ == '__main__':
    main()