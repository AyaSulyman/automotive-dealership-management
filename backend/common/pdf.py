"""
Minimal shared PDF renderer used by:
  - sales.SalesInvoice PDF (GET /sales-invoices/{id}/pdf)
  - payments.Payment receipt (GET /payments/{id}/receipt)
  - payments.Statement PDF (POST /statements/generate, GET /statements/{id})

Kept deliberately simple (title + key/value header + a line-items table)
since the BRD's requirement is a professional-looking, printable document,
not a pixel-perfect branded template.
"""
import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet


def render_simple_document(title, subtitle, meta_pairs, table_headers, table_rows, totals=None, footer_note=None):
    """
    title: str — big heading, e.g. "INVOICE" / "PAYMENT RECEIPT" / "CUSTOMER STATEMENT"
    subtitle: str — e.g. "Invoice #INV-2024-0001"
    meta_pairs: list[(label, value)] — printed as a two-column key/value block
    table_headers: list[str]
    table_rows: list[list[str]]
    totals: list[(label, value)] | None — printed right-aligned below the table
    footer_note: str | None
    Returns: bytes (PDF)
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, topMargin=0.6 * inch, bottomMargin=0.6 * inch)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph(f"<b>{title}</b>", styles["Title"]))
    if subtitle:
        story.append(Paragraph(subtitle, styles["Heading3"]))
    story.append(Spacer(1, 12))

    if meta_pairs:
        meta_table = Table([[f"<b>{k}</b>", v] for k, v in meta_pairs], colWidths=[2 * inch, 4 * inch])
        meta_table.setStyle(TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        # Paragraph-wrap the bold labels
        meta_table._cellvalues = [[Paragraph(str(c), styles["Normal"]) for c in row] for row in meta_table._cellvalues]
        story.append(meta_table)
        story.append(Spacer(1, 16))

    if table_headers and table_rows:
        data = [table_headers] + table_rows
        t = Table(data, repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E79")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#B7B7B7")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F2F2F2")]),
            ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
        ]))
        story.append(t)
        story.append(Spacer(1, 12))

    if totals:
        totals_table = Table([[k, v] for k, v in totals], colWidths=[4.5 * inch, 1.5 * inch])
        totals_table.setStyle(TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("LINEABOVE", (0, -1), (-1, -1), 0.75, colors.black),
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ]))
        story.append(totals_table)

    if footer_note:
        story.append(Spacer(1, 24))
        story.append(Paragraph(footer_note, styles["Italic"]))

    doc.build(story)
    return buf.getvalue()
