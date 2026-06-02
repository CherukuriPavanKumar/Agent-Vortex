from typing import Annotated
from pathlib import Path

import weasyprint
from langchain_core.tools import tool


PDF_OUTPUT_DIR = Path("generated_pdfs")


@tool
def generate_pdf(
    html_content: Annotated[
        str,
        "The HTML content to convert to PDF. Construct clean, well-formatted HTML/CSS.",
    ],
    output_path: Annotated[
        str,
        "Desired PDF filename (e.g. report.pdf). Files are always stored in generated_pdfs/.",
    ],
) -> str:
    """
    Generate a PDF file from HTML using WeasyPrint.

    Security:
    - All PDFs are written into generated_pdfs/
    - Path traversal is prevented
    - Arbitrary filesystem writes are not allowed

    Reliability:
    - Validates input HTML
    - Confirms file creation
    - Confirms file is non-empty
    """

    try:
        if not html_content.strip():
            return "PDF generation failed: HTML content is empty."

        # Ensure output directory exists
        PDF_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        # Extract only the filename to prevent path traversal
        filename = Path(output_path).name

        # Ensure .pdf extension
        if not filename.lower().endswith(".pdf"):
            filename += ".pdf"

        final_path = PDF_OUTPUT_DIR / filename

        # Generate PDF
        weasyprint.HTML(string=html_content).write_pdf(str(final_path))

        # Verify file exists
        if not final_path.exists():
            return (
                f"PDF generation failed: file was not created at "
                f"'{final_path}'. WeasyPrint may have encountered a rendering error."
            )

        # Verify file is not empty
        file_size = final_path.stat().st_size

        if file_size == 0:
            return (
                f"PDF generation failed: file '{final_path}' is empty (0 bytes). "
                "Check the HTML content for rendering issues."
            )

        return (
            f"Successfully generated PDF file.\n"
            f"Location: {final_path.resolve()}\n"
            f"Size: {file_size} bytes"
        )

    except Exception as e:
        return f"Failed to generate PDF: {e}"