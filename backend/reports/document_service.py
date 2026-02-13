"""
Document Service — facade for document generation.
Currently supports PDF, extensible for future formats.
"""

from datetime import datetime
from backend.reports.pdf_generator import PdfGenerator


class DocumentService:
    """High-level document generation service."""

    def __init__(self):
        self.pdf_generator = PdfGenerator()

    def generate_pdf(self, report_plan: dict, dataframe, insights: str,
                     user_context: dict) -> str:
        """
        Generate a PDF report.
        Returns the filename (not full path) for download URL construction.
        """
        username = user_context.get("username", "unknown")
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        filename = f"report_{username}_{timestamp}.pdf"

        self.pdf_generator.generate(report_plan, dataframe, insights, user_context, filename)

        return filename

    def generate(self, format: str, report_plan: dict, dataframe,
                 insights: str, user_context: dict) -> str:
        """
        Generate a document in the specified format.
        Currently only PDF is supported; future formats can be added here.
        """
        if format.lower() != "pdf":
            print(f"WARNING: Unsupported format '{format}' requested. Defaulting to PDF.")

        return self.generate_pdf(report_plan, dataframe, insights, user_context)
