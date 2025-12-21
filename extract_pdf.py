#!/usr/bin/env python3
"""
Simple PDF text extraction script.
Extracts text from PDF files and saves to .txt files.

Usage:
    python extract_pdf.py <pdf_file1> [pdf_file2 ...]

Example:
    python extract_pdf.py document.pdf
    python extract_pdf.py file1.pdf file2.pdf
"""

import sys
import os
from pathlib import Path

try:
    from pypdf import PdfReader
except ImportError:
    print("Error: pypdf library not found.")
    print("Install it with: pip install pypdf")
    sys.exit(1)


def extract_pdf_text(pdf_path):
    """Extract text from a PDF file."""
    try:
        reader = PdfReader(pdf_path)
        text_content = []

        print(f"\nProcessing: {pdf_path}")
        print(f"Total pages: {len(reader.pages)}")

        for i, page in enumerate(reader.pages, 1):
            if i % 10 == 0:  # Progress indicator every 10 pages
                print(f"  Processed {i}/{len(reader.pages)} pages...")
            text_content.append(page.extract_text())

        return "\n\n".join(text_content)

    except Exception as e:
        print(f"Error processing {pdf_path}: {e}")
        return None


def main():
    if len(sys.argv) < 2:
        print("Usage: python extract_pdf.py <pdf_file1> [pdf_file2 ...]")
        sys.exit(1)

    pdf_files = sys.argv[1:]

    for pdf_file in pdf_files:
        pdf_path = Path(pdf_file)

        if not pdf_path.exists():
            print(f"Error: File not found: {pdf_file}")
            continue

        if not pdf_path.suffix.lower() == '.pdf':
            print(f"Warning: {pdf_file} doesn't appear to be a PDF file")
            continue

        # Extract text
        text = extract_pdf_text(pdf_path)

        if text:
            # Create output filename
            output_path = pdf_path.with_suffix('.txt')

            # Write to file
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(text)

            print(f"✓ Extracted to: {output_path}")
            print(f"  Text length: {len(text)} characters")
        else:
            print(f"✗ Failed to extract text from {pdf_file}")


if __name__ == "__main__":
    main()
