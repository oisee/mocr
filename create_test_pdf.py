import os
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

def create_sample_pdf(output_path="./in/sample.pdf"):
    # Ensure the directory exists
    os.makedirs("./in", exist_ok=True)
    
    # Create a canvas with letter size
    c = canvas.Canvas(output_path, pagesize=letter)
    
    # Add a title
    c.setFont("Helvetica-Bold", 16)
    c.drawString(100, 750, "Sample PDF Document")
    
    # Add some paragraphs of text
    c.setFont("Helvetica", 12)
    c.drawString(100, 700, "This is a sample PDF document created for testing the MOCR application.")
    c.drawString(100, 680, "It contains some basic text that can be processed by the OCR system.")
    
    # Add a simple bullet list
    c.drawString(100, 640, "• First item in a list")
    c.drawString(100, 620, "• Second item in a list")
    c.drawString(100, 600, "• Third item in a list")
    
    # Add a simple table header
    c.setFont("Helvetica-Bold", 12)
    c.drawString(100, 560, "Column 1")
    c.drawString(250, 560, "Column 2")
    c.drawString(400, 560, "Column 3")
    
    # Add table content
    c.setFont("Helvetica", 12)
    c.drawString(100, 540, "Data 1")
    c.drawString(250, 540, "Data 2")
    c.drawString(400, 540, "Data 3")
    
    c.drawString(100, 520, "Data 4")
    c.drawString(250, 520, "Data 5")
    c.drawString(400, 520, "Data 6")


# Add an image
    image_path = "./image01.png"
    if os.path.exists(image_path):
        c.drawImage(image_path, 300, 200, width=200, height=200)
    

    # Add a sentence at the bottom
    c.drawString(100, 100, "This is the last sentence in the document for testing purposes.")
    
    # Save the PDF
    c.save()
    
    print(f"Sample PDF created at: {output_path}")

if __name__ == "__main__":
    create_sample_pdf()