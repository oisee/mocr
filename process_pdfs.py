import os
import sys
import glob
import base64
import requests
import json
from mistralai import Mistral
from pathlib import Path
import argparse
import re
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO

def extract_images_from_pdf(pdf_path, output_folder, debug=False):
    """Extract images directly from a PDF file using PyPDF2."""
    # Skip if PyPDF2 isn't available
    try:
        import PyPDF2
        from PyPDF2.filters import _xobj_to_image
    except ImportError:
        if debug:
            print("PyPDF2 not available for direct PDF extraction")
        return {}
    
    extracted_images = {}
    
    try:
        with open(pdf_path, 'rb') as file:
            pdf = PyPDF2.PdfReader(file)
            
            # Extract images from each page
            for page_num, page in enumerate(pdf.pages):
                if '/Resources' in page and '/XObject' in page['/Resources']:
                    x_objects = page['/Resources']['/XObject']
                    
                    # Process each XObject that might be an image
                    for obj_name, obj in x_objects.items():
                        if obj['/Subtype'] == '/Image':
                            # Get image data
                            img_data = None
                            try:
                                if '/Filter' in obj:
                                    filters = obj['/Filter']
                                    if isinstance(filters, list):
                                        img_data = _xobj_to_image(obj)
                                    elif filters == '/DCTDecode':  # JPEG
                                        img_data = obj._data
                                    elif filters == '/FlateDecode':  # PNG
                                        img_data = obj._data
                                    elif filters == '/JPXDecode':  # JPEG2000
                                        img_data = obj._data
                                else:
                                    img_data = obj._data
                            except Exception as e:
                                if debug:
                                    print(f"  Error extracting image: {str(e)}")
                                continue
                            
                            if img_data:
                                # Generate a unique name for this image
                                img_id = f"pdf_img_{page_num}_{obj_name.replace('/', '_')}"
                                img_path = os.path.join(output_folder, f"{img_id}.jpg")
                                
                                try:
                                    with open(img_path, 'wb') as img_file:
                                        img_file.write(img_data)
                                    extracted_images[img_id] = img_path
                                    if debug:
                                        print(f"  ✓ Extracted PDF image: {img_id}")
                                except Exception as e:
                                    if debug:
                                        print(f"  ✗ Error saving PDF image {img_id}: {str(e)}")
        
        return extracted_images
    
    except Exception as e:
        if debug:
            print(f"Error in PDF image extraction: {str(e)}")
        return {}

def process_pdfs(dry_run=False, debug=False, extract_pdf_images=False):
    # Check if API key is set (unless in dry run mode)
    api_key = os.environ.get("MISTRAL_API_KEY")
    if not api_key and not dry_run:
        print("Error: MISTRAL_API_KEY environment variable not set")
        sys.exit(1)
    
    # Initialize client (if not in dry run mode)
    client = None
    if not dry_run:
        client = Mistral(api_key=api_key)
    
    # Create folders if they don't exist
    os.makedirs("./in", exist_ok=True)
    os.makedirs("./out", exist_ok=True)
    
    # Get all PDF files in the in folder
    pdf_files = glob.glob("./in/*.pdf")
    
    if not pdf_files:
        print("No PDF files found in ./in folder")
        return
    
    print(f"Found {len(pdf_files)} PDF files to process")
    
    for pdf_file in pdf_files:
        filename = os.path.basename(pdf_file)
        file_stem = Path(filename).stem
        print(f"Processing: {filename}")
        
        # Create subfolder with the same name as the markdown file
        resource_folder = os.path.join("./out", file_stem)
        os.makedirs(resource_folder, exist_ok=True)
        
        try:
            if dry_run:
                print(f"[DRY RUN] Would process {filename}")
                # Create a dummy markdown file for testing
                output_path = os.path.join("./out", f"{file_stem}.md")
                with open(output_path, "w", encoding="utf-8") as out_file:
                    out_file.write(f"# Dummy content for {filename}\n\nThis is a dry run test.")
                print(f"✓ [DRY RUN] Created dummy output at {output_path}")
                continue
            
            # Upload the file
            with open(pdf_file, "rb") as f:
                uploaded_pdf = client.files.upload(
                    file={
                        "file_name": filename,
                        "content": f,
                    },
                    purpose="ocr"
                )
            
            # Get signed URL
            signed_url = client.files.get_signed_url(file_id=uploaded_pdf.id)
            
            # Process with OCR
            ocr_response = client.ocr.process(
                model="mistral-ocr-latest",
                document={
                    "type": "document_url",
                    "document_url": signed_url.url,
                }
            )
            
            # Debug: Print OCR response structure to understand image data
            if debug:
                print(f"OCR Response for {filename}:")
                print(f"  Number of pages: {len(ocr_response.pages)}")
                for i, page in enumerate(ocr_response.pages[:1]):  # Just examine first page for debugging
                    print(f"  Page {i+1} attributes: {dir(page)}")
                    if hasattr(page, 'images'):
                        print(f"  Page {i+1} has {len(page.images)} images")
                        for j, img in enumerate(page.images[:1]):  # Just examine first image for debugging
                            print(f"    Image {j+1} attributes: {dir(img)}")
                            print(f"    Image {j+1} id: {img.id}")
                            # Check if image has base64 data and what attributes are available
                            if hasattr(img, 'image_base64'):
                                print(f"    Image {j+1} has image_base64: {img.image_base64 is not None}")
                                if img.image_base64 is not None:
                                    print(f"    Image {j+1} base64 data length: {len(img.image_base64)}")
                            if hasattr(img, 'top_left_x'):
                                print(f"    Image {j+1} has position data: ({img.top_left_x}, {img.top_left_y}) to ({img.bottom_right_x}, {img.bottom_right_y})")
            
            # Extract images directly from PDF if requested
            pdf_images = {}
            if extract_pdf_images:
                if debug:
                    print(f"Attempting to extract images directly from PDF: {filename}")
                pdf_images = extract_images_from_pdf(pdf_file, resource_folder, debug=debug)
                if pdf_images and debug:
                    print(f"Extracted {len(pdf_images)} images directly from PDF")
            
            # Function to create a placeholder image
            def create_placeholder_image(img_id, width=400, height=300):
                # Create a blank image with a light gray background
                img = Image.new('RGB', (width, height), color=(240, 240, 240))
                
                # Get a drawing context
                draw = ImageDraw.Draw(img)
                
                # Draw a border
                draw.rectangle([(0, 0), (width-1, height-1)], outline=(200, 200, 200), width=2)
                
                # Draw diagonal lines
                draw.line([(0, 0), (width, height)], fill=(200, 200, 200), width=2)
                draw.line([(0, height), (width, 0)], fill=(200, 200, 200), width=2)
                
                # Add image ID text
                try:
                    # Use a system font if available
                    font = ImageFont.truetype("Arial", 20)
                except IOError:
                    # Fall back to default font
                    font = ImageFont.load_default()
                
                text = f"Image placeholder: {img_id}"
                # Get text width - method depends on Pillow version
                try:
                    # For newer Pillow versions
                    text_width = draw.textlength(text, font=font)
                except AttributeError:
                    # Fallback for older Pillow versions
                    text_width = font.getsize(text)[0] if hasattr(font, 'getsize') else width//2
                
                # Calculate center position
                text_x = (width - text_width) // 2
                text_y = height // 2
                
                # Draw text
                draw.text(
                    (text_x, text_y), 
                    text,
                    fill=(100, 100, 100),
                    font=font
                )
                
                buffer = BytesIO()
                img.save(buffer, format="JPEG")
                return buffer.getvalue()

            # Save images from the OCR response
            images = {}
            image_ids = []
            
            # First pass: collect all image IDs from markdown
            for page_idx, page in enumerate(ocr_response.pages):
                if hasattr(page, 'markdown'):
                    # Extract image IDs from markdown using regex
                    img_matches = re.findall(r'!\[(.*?)\]\((.*?)\)', page.markdown)
                    for alt_text, img_src in img_matches:
                        # Extract just the ID part (remove any file extension)
                        img_id = os.path.splitext(img_src)[0]
                        if img_id not in image_ids:
                            image_ids.append(img_id)
                            images[img_id] = {
                                'data': None,
                                'filename': f"{img_id}.jpeg",
                                'extracted': False
                            }
            
            # Second pass: extract image data from the OCR response
            for page_idx, page in enumerate(ocr_response.pages):
                if hasattr(page, 'images') and page.images:
                    for img_idx, image in enumerate(page.images):
                        img_id = image.id
                        
                        # Different versions of the API might store image data differently
                        # Try several possible attributes where image data might be stored
                        img_data = None
                        
                        # Check for image_base64 attribute first (documented API)
                        if hasattr(image, 'image_base64') and image.image_base64 is not None:
                            img_data = image.image_base64
                            if debug:
                                print(f"  Found image data in image_base64 for {img_id}")
                        
                        # If no direct base64 data, check if there are other potential data attributes
                        elif hasattr(image, 'data') and image.data is not None:
                            img_data = image.data
                            if debug:
                                print(f"  Found image data in 'data' attribute for {img_id}")
                        
                        # As a last resort, if we have position data for the image, extract from PDF
                        # (This would require additional PDF parsing tools, omitted for simplicity)
                        
                        # Create the extension based on the ID or default to jpeg
                        ext = img_id.split('.')[-1] if '.' in img_id else 'jpeg'
                        
                        # Add or update the image in our collection
                        images[img_id] = {
                            'data': img_data,
                            'filename': f"{img_id}.{ext}",
                            'extracted': True,
                            'image_object': image  # Store the full image object for reference
                        }
            
            # Save all images to the resource folder
            for img_id, img_info in images.items():
                img_path = os.path.join(resource_folder, img_info['filename'])
                saved = False
                
                try:
                    # Method 1: Use base64 data if available
                    if img_info['data'] is not None:
                        with open(img_path, "wb") as img_file:
                            img_file.write(base64.b64decode(img_info['data']))
                        print(f"  ✓ Saved image from base64: {img_info['filename']}")
                        saved = True
                    
                    # Method 2: Try to access image directly from the image object
                    elif 'image_object' in img_info and hasattr(img_info['image_object'], 'image'):
                        img_obj = img_info['image_object'].image
                        if isinstance(img_obj, bytes):
                            with open(img_path, "wb") as img_file:
                                img_file.write(img_obj)
                            print(f"  ✓ Saved image from bytes: {img_info['filename']}")
                            saved = True
                    
                    # Method 3: If position data is available, try to extract from OCR response
                    elif ('image_object' in img_info and 
                          hasattr(img_info['image_object'], 'top_left_x') and
                          hasattr(img_info['image_object'], 'top_left_y') and
                          hasattr(img_info['image_object'], 'bottom_right_x') and
                          hasattr(img_info['image_object'], 'bottom_right_y')):
                        
                        if debug:
                            print(f"  Image {img_id} has coordinates but no data")
                        
                        # Method 4: If we have coordinates but no data, try using directly extracted PDF images
                        if not saved and pdf_images:
                            # Find an image from the PDF that might match (this is a simple approach)
                            # In a real implementation, you would match based on coordinates
                            pdf_img_id = next(iter(pdf_images.keys()))
                            pdf_img_path = pdf_images[pdf_img_id]
                            
                            try:
                                # Copy the PDF image to our target path
                                with open(pdf_img_path, 'rb') as src_file:
                                    with open(img_path, 'wb') as dest_file:
                                        dest_file.write(src_file.read())
                                print(f"  ✓ Used image extracted from PDF: {img_info['filename']}")
                                saved = True
                                
                                # Remove this image from the pool so we don't use it again
                                if pdf_img_id in pdf_images:
                                    del pdf_images[pdf_img_id]
                            except Exception as e:
                                if debug:
                                    print(f"  ✗ Error using PDF image: {str(e)}")
                        
                        # If we still haven't saved an image, create a placeholder with actual dimensions
                        if not saved:
                            img_obj = img_info['image_object']
                            width = img_obj.bottom_right_x - img_obj.top_left_x
                            height = img_obj.bottom_right_y - img_obj.top_left_y
                            placeholder_data = create_placeholder_image(
                                img_id, 
                                width=max(100, min(800, int(width))), 
                                height=max(100, min(800, int(height)))
                            )
                            with open(img_path, "wb") as img_file:
                                img_file.write(placeholder_data)
                            print(f"  ✓ Created placeholder with actual dimensions: {img_info['filename']}")
                            saved = True
                    
                    # Method 5: Try using any remaining extracted PDF images 
                    if not saved and pdf_images:
                        pdf_img_id = next(iter(pdf_images.keys()))
                        pdf_img_path = pdf_images[pdf_img_id]
                        
                        try:
                            # Copy the PDF image to our target path
                            with open(pdf_img_path, 'rb') as src_file:
                                with open(img_path, 'wb') as dest_file:
                                    dest_file.write(src_file.read())
                            print(f"  ✓ Used remaining PDF image for: {img_info['filename']}")
                            saved = True
                            
                            # Remove this image from the pool so we don't use it again
                            if pdf_img_id in pdf_images:
                                del pdf_images[pdf_img_id]
                        except Exception as e:
                            if debug:
                                print(f"  ✗ Error using PDF image: {str(e)}")
                    
                    # If all methods fail, create a generic placeholder
                    if not saved:
                        placeholder_data = create_placeholder_image(img_id)
                        with open(img_path, "wb") as img_file:
                            img_file.write(placeholder_data)
                        print(f"  ✓ Created generic placeholder: {img_info['filename']}")
                
                except Exception as img_err:
                    print(f"  ✗ Error saving image {img_id}: {str(img_err)}")
                    # Try to create a placeholder as a fallback
                    try:
                        placeholder_data = create_placeholder_image(img_id)
                        with open(img_path, "wb") as img_file:
                            img_file.write(placeholder_data)
                        print(f"  ✓ Created fallback placeholder: {img_info['filename']}")
                    except Exception as placeholder_err:
                        print(f"  ✗ Failed to create placeholder for {img_id}: {str(placeholder_err)}")
            
            # Process markdown and update image paths to point to the resource folder
            combined_markdown = ""
            for page in ocr_response.pages:
                page_markdown = page.markdown
                
                # Update all image references to point to the correct relative path
                # Match pattern: ![alt](img_id) or ![alt](img_id.ext)
                for img_id in images.keys():
                    base_id = os.path.splitext(img_id)[0]  # Remove extension if present
                    img_filename = images[img_id]['filename']
                    
                    # Create patterns to match various forms of the image reference
                    patterns = [
                        f'!\\[.*?\\]\\({re.escape(img_id)}\\)',  # ![alt](img_id)
                        f'!\\[.*?\\]\\({re.escape(base_id)}\\)'  # ![alt](base_id) without extension
                    ]
                    
                    # Try to replace each pattern
                    for pattern in patterns:
                        replacement = f'![{img_id}]({file_stem}/{img_filename})'
                        page_markdown = re.sub(pattern, replacement, page_markdown)
                
                combined_markdown += page_markdown + "\n\n"
            
            # Save markdown content to output file
            output_path = os.path.join("./out", f"{file_stem}.md")
            with open(output_path, "w", encoding="utf-8") as out_file:
                out_file.write(combined_markdown)
            
            print(f"✓ Processed and saved to {output_path}")
            print(f"✓ Resources saved to {resource_folder}")
            
        except Exception as e:
            print(f"Error processing {filename}: {str(e)}")
    
    print("Processing complete!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process PDF files with Mistral OCR")
    parser.add_argument("--dry-run", action="store_true", help="Run without making API calls")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    parser.add_argument("--extract-pdf-images", action="store_true", help="Use PyPDF2 to extract images directly from PDF files")
    args = parser.parse_args()
    
    # If extract-pdf-images is set, ensure we have PyPDF2
    if args.extract_pdf_images:
        try:
            import PyPDF2
        except ImportError:
            print("PyPDF2 library not installed. Install with: pip install PyPDF2")
            print("Continuing without direct PDF image extraction.")
            args.extract_pdf_images = False
    
    process_pdfs(dry_run=args.dry_run, debug=args.debug, extract_pdf_images=args.extract_pdf_images)