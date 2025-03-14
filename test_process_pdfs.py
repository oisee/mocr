import os
import unittest
from unittest.mock import patch, MagicMock
import tempfile
from pathlib import Path
import sys
from io import StringIO

# Import the module to test
import process_pdfs

class TestProcessPDFs(unittest.TestCase):
    
    def setUp(self):
        # Create temporary directories for testing
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_in_dir = os.path.join(self.temp_dir.name, "in")
        self.test_out_dir = os.path.join(self.temp_dir.name, "out")
        os.makedirs(self.test_in_dir, exist_ok=True)
        os.makedirs(self.test_out_dir, exist_ok=True)
        
        # Create a dummy PDF file for testing
        self.test_pdf_path = os.path.join(self.test_in_dir, "test.pdf")
        with open(self.test_pdf_path, "wb") as f:
            f.write(b"%PDF-1.4\n%Test dummy PDF content")
    
    def tearDown(self):
        self.temp_dir.cleanup()
    
    @patch.dict(os.environ, {"MISTRAL_API_KEY": "test_api_key"})
    @patch("process_pdfs.Mistral")
    @patch("process_pdfs.glob.glob")
    def test_process_pdfs_success(self, mock_glob, mock_mistral_class):
        # Mock the glob to return our test PDF
        mock_glob.return_value = [self.test_pdf_path]
        
        # Set up mock for Mistral client
        mock_client = MagicMock()
        mock_mistral_class.return_value = mock_client
        
        # Mock file upload response
        mock_upload_response = MagicMock()
        mock_upload_response.id = "test_file_id"
        mock_client.files.upload.return_value = mock_upload_response
        
        # Mock signed URL response
        mock_signed_url_response = MagicMock()
        mock_signed_url_response.url = "https://test-signed-url.com"
        mock_client.files.get_signed_url.return_value = mock_signed_url_response
        
        # Mock OCR process response
        mock_ocr_response = MagicMock()
        mock_ocr_response.text = "# Test Markdown Content"
        mock_client.ocr.process.return_value = mock_ocr_response
        
        # Capture stdout for verification
        captured_output = StringIO()
        sys.stdout = captured_output
        
        # Patch the directory paths
        with patch("process_pdfs.glob.glob", return_value=[self.test_pdf_path]):
            with patch("builtins.open", new_callable=unittest.mock.mock_open()):
                # Run the function
                process_pdfs.process_pdfs()
        
        # Restore stdout
        sys.stdout = sys.__stdout__
        
        # Verify function calls
        mock_client.files.upload.assert_called_once()
        mock_client.files.get_signed_url.assert_called_once_with(file_id="test_file_id")
        mock_client.ocr.process.assert_called_once_with(
            model="mistral-ocr-latest",
            document={
                "type": "document_url",
                "document_url": "https://test-signed-url.com",
            }
        )
        
        # Check output contains success message
        self.assertIn("Processing: test.pdf", captured_output.getvalue())
        self.assertIn("Processing complete!", captured_output.getvalue())
    
    @patch.dict(os.environ, {}, clear=True)  # Clear MISTRAL_API_KEY
    def test_missing_api_key(self):
        # Capture stdout and stderr for verification
        captured_output = StringIO()
        captured_error = StringIO()
        sys.stdout = captured_output
        sys.stderr = captured_error
        
        # Test with sys.exit mocked to prevent actual exit
        with self.assertRaises(SystemExit) as cm:
            process_pdfs.process_pdfs()
        
        # Restore stdout and stderr
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__
        
        # Check exit code
        self.assertEqual(cm.exception.code, 1)
        
        # Check error message
        self.assertIn("Error: MISTRAL_API_KEY environment variable not set", captured_output.getvalue())

if __name__ == "__main__":
    unittest.main()