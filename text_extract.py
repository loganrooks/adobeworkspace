import argparse
import json
from pathlib import Path
import zipfile


def extract_text_and_headers(zip_path, output_txt_path=None):
    """
    Extract text and headers from the ZIP file produced by Adobe Extract API,
    excluding footnotes, and save to a text file.
    
    Args:
        zip_path: Path to the ZIP file containing extracted PDF content
        output_txt_path: Path where to save the extracted text
    """
    # Open and read the ZIP file
    with zipfile.ZipFile(zip_path, 'r') as archive:
        # Read the structured data JSON
        with archive.open('structuredData.json') as jsonentry:
            data = json.loads(jsonentry.read())
        
        # Extract text content
        content = []
        for element in data["elements"]:
            # Skip footnotes by checking the Path
            if "Footnote" in element.get("Path", ""):
                continue
                
            # Get headers and text content
            if element.get("Text"):
                if "H1" in element.get("Path", ""):
                    content.append(f"\n\n# {element['Text']} \n")
                elif "H2" in element.get("Path", ""):
                    content.append(f"\n# {element['Text']} \n")
                elif "H3" in element.get("Path", ""):
                    content.append(f"\n# {element['Text']} \n")
                else:
                    content.append(element["Text"])
            
        if output_txt_path is None:
            input_path = Path(zip_path)
            output_txt_path = str(input_path.with_suffix('.txt'))
            
        # Write the content to a text file
        with open(output_txt_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(content))
        
        print(f"Extracted text saved to: {output_txt_path}")

def main():
    parser = argparse.ArgumentParser(description='Extract text and headers from PDF')
    parser.add_argument('zip_path', type=str, help='Path to the ZIP file containing extracted PDF content')
    parser.add_argument('--output', '-o', type=str, help='Optional output text file path', default=None)

    args = parser.parse_args()
    
    extract_text_and_headers(args.zip_path, args.output)

if __name__ == '__main__':
    main()