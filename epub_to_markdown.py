import os
import re
import argparse
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
from markdownify import markdownify as md

def sanitize_filename(name):
    """Removes or replaces characters invalid for filenames."""
    # Remove invalid characters
    name = re.sub(r'[\\/*?:"<>|]', '', name)
    # Replace spaces with underscores
    name = name.replace(' ', '_')
    # Limit length if necessary (optional)
    # max_len = 100
    # if len(name) > max_len:
    #     name = name[:max_len]
    return name

def format_author_name(author_string):
    """Attempts to format author name as LastnameFirstname."""
    parts = author_string.split()
    if len(parts) > 1:
        # Simple assumption: last word is lastname
        lastname = parts[-1]
        firstname = "".join(parts[:-1])
        return f"{lastname}{firstname}"
    elif len(parts) == 1:
        # Only one name found, use it as is
        return parts[0]
    else:
        return "UnknownAuthor"

def epub_to_markdown(epub_path, output_dir):
    """
    Converts an EPUB file to a Markdown file.

    Args:
        epub_path (str): Path to the input EPUB file.
        output_dir (str): Directory to save the output Markdown file.
    """
    try:
        print(f"Processing '{os.path.basename(epub_path)}'...")
        book = epub.read_epub(epub_path)

        # --- Extract Metadata ---
        title = "UnknownTitle"
        authors = ["UnknownAuthor"]

        # Try standard metadata fields
        metadata_title = book.get_metadata('DC', 'title')
        if metadata_title:
            title = metadata_title[0][0]

        metadata_creator = book.get_metadata('DC', 'creator')
        if metadata_creator:
            # Handle multiple authors if present, join them for filename
            authors = [author[0] for author in metadata_creator]

        # Format author string for filename (simple approach)
        if len(authors) == 1:
            formatted_author = format_author_name(authors[0])
        else:
            # Join multiple authors, e.g., SmithJohn_DoeJane
            formatted_author = "_".join(format_author_name(a) for a in authors)

        # Sanitize title and author for filename
        safe_title = sanitize_filename(title)
        safe_author = sanitize_filename(formatted_author)

        output_filename = f"{safe_author}_{safe_title}.md"
        output_filepath = os.path.join(output_dir, output_filename)

        print(f"  Title: {title}")
        print(f"  Author(s): {', '.join(authors)}")
        print(f"  Output Filename: {output_filename}")

        # --- Extract and Convert Content ---
        markdown_content = []
        items = list(book.get_items_of_type(ebooklib.ITEM_DOCUMENT))

        # Add Title and Author at the beginning
        markdown_content.append(f"# {title}")
        markdown_content.append(f"**By: {', '.join(authors)}**\n\n---\n")

        for item in items:
            try:
                soup = BeautifulSoup(item.get_body_content(), 'html.parser')
                # Extract text content, convert to Markdown
                # Use heading_style='ATX' for '#' style headings
                # Use strip=['a'] to remove links if desired, or keep them
                content_md = md(str(soup), heading_style='ATX', strip=[])
                markdown_content.append(content_md)
                markdown_content.append("\n\n---\n\n") # Add separator between chapters/sections
            except Exception as e:
                print(f"  Warning: Could not process item {item.get_name()}. Error: {e}")

        # Remove the last separator
        if markdown_content and markdown_content[-1].strip() == "---":
            markdown_content.pop()

        # --- Write Output ---
        os.makedirs(output_dir, exist_ok=True)
        with open(output_filepath, 'w', encoding='utf-8') as f:
            f.write('\n'.join(markdown_content))

        print(f"  Successfully converted to '{output_filepath}'")
        return True

    except FileNotFoundError:
        print(f"Error: EPUB file not found at '{epub_path}'")
        return False
    except Exception as e:
        print(f"Error processing '{os.path.basename(epub_path)}': {e}")
        # Consider logging the full traceback here for debugging
        # import traceback
        # traceback.print_exc()
        return False

def main():
    parser = argparse.ArgumentParser(description='Convert EPUB file(s) to Markdown.')
    parser.add_argument('input_path', help='Path to the input EPUB file or a directory containing EPUB files.')
    parser.add_argument('output_dir', help='Directory to save the output Markdown file(s).')

    args = parser.parse_args()

    if not os.path.exists(args.input_path):
        print(f"Error: Input path '{args.input_path}' not found.")
        return

    success_count = 0
    fail_count = 0

    if os.path.isdir(args.input_path):
        print(f"Processing directory: {args.input_path}")
        for filename in os.listdir(args.input_path):
            if filename.lower().endswith('.epub'):
                epub_file_path = os.path.join(args.input_path, filename)
                if epub_to_markdown(epub_file_path, args.output_dir):
                    success_count += 1
                else:
                    fail_count += 1
    elif os.path.isfile(args.input_path) and args.input_path.lower().endswith('.epub'):
        print(f"Processing single file: {args.input_path}")
        if epub_to_markdown(args.input_path, args.output_dir):
            success_count += 1
        else:
            fail_count += 1
    else:
        print(f"Error: Input path '{args.input_path}' is not a valid EPUB file or directory.")
        return

    print("\n--- Summary ---")
    print(f"Successfully converted: {success_count}")
    print(f"Failed conversions:   {fail_count}")

if __name__ == '__main__':
    main()