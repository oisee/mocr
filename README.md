# MOCR - Mistral OCR PDF Processor

A simple application that uses Mistral AI's OCR capabilities to process PDF files and convert them to markdown format.

## Setup

1. Install the required packages:
```
pip install mistralai
```

2. Set your Mistral API key as an environment variable:
```
export MISTRAL_API_KEY="your_api_key_here"
```

## Usage

1. Place your PDF files in the `./in` folder
2. Run the script:
```
python process_pdfs.py
```
3. Find the processed markdown files in the `./out` folder

For testing without making API calls:
```
python process_pdfs.py --dry-run
```

Running unit tests:
```
python -m unittest test_process_pdfs.py
```

Creating a sample PDF for testing:
```
python create_test_pdf.py
```

## Requirements

- Python 3.6+
- mistralai Python package
- A valid Mistral AI API key

## Limitations

- PDF files must not exceed 50 MB in size
- Documents should be no longer than 1,000 pages