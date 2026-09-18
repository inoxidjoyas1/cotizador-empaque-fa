"""Genera la cotización de empaque como PDF (reportlab) y como imagen PNG
(renderizando ese mismo PDF con pypdfium2).

Ambas librerías son puro-Python con wheels para Linux, así que funcionan en
Streamlit Community Cloud sin dependencias del sistema (no necesita poppler).

Uso:
    pdf = construir_pdf(meta, filas, subtotal, total)
    png = pdf_a_png(pdf)          # opcional
"""
from __future__ import annotations

import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

NAV = colors.HexColor("#1F4E78")
SOFT = colors.HexColor("#EAF0F7")
LINE = colors.HexColor("#DDE6F0")
GREEN_BG = colors.HexColor("#E3F1DA")
GREEN_TX = colors.HexColor("#2F6B2F")
INK = colors.HexColor("#1A2530")


def _fmt(n: float) -> str:
    return f"${n:,.2f}"


def construir_pdf(meta: dict, filas: list[dict], subtotal: float, total: float) -> bytes:
    """meta: {cliente, folio, fecha, lista}. filas: [{clave, descr, linea, cant, pu, importe}]."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        leftMargin=16 * mm, rightMargin=16 * mm,
        topMargin=14 * mm, bottomMargin=14 * mm,
        title="Cotizacion de empaque",
    )
    st_h1 = ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=18,
                           textColor=NAV, leading=22, spaceAfter=5)
    st_sub = ParagraphStyle("sub", fontName="Helvetica", fontSize=9,
                            textColor=colors.HexColor("#6b7c90"))
    st_meta = ParagraphStyle("meta", fontName="Helvetica", fontSize=10, textColor=INK,
                             leading=15)
    st_cell = ParagraphStyle("cell", fontName="Helvetica", fontSize=9, textColor=INK,
                             leading=11)
    st_cellb = ParagraphStyle("cellb", fontName="Helvetica-Bold", fontSize=9,
                              textColor=INK, leading=11)
    st_foot = ParagraphStyle("foot", fontName="Helvetica", fontSize=8,
                             textColor=colors.HexColor("#8a99aa"))

    story: list = []
    story.append(Paragraph("INOXIDJOYAS", st_h1))
    story.append(Paragraph("Cotización de empaque (líneas F y A)", st_sub))
    story.append(Spacer(1, 8))

    # Bloque de datos cliente / folio / fecha
    datos = []
    if meta.get("cliente"):
        datos.append(f"<b>Cliente:</b> {meta['cliente']}")
    if meta.get("folio"):
        datos.append(f"<b>Folio:</b> {meta['folio']}")
    datos.append(f"<b>Fecha:</b> {meta.get('fecha', '')}")
    datos.append(f"<b>Lista:</b> {meta.get('lista', '')} (sin IVA)")
    story.append(Paragraph(" &nbsp;·&nbsp; ".join(datos), st_meta))
    story.append(Spacer(1, 10))

    # Tabla de partidas
    head = ["Clave", "Descripción", "Cant.", "P. Unit.", "Importe"]
    data = [[Paragraph(f"<b>{h}</b>", st_cellb) for h in head]]
    for f in filas:
        data.append([
            Paragraph(str(f["clave"]), st_cell),
            Paragraph(str(f["descr"]), st_cell),
            Paragraph(str(f["cant"]), st_cell),
            Paragraph(_fmt(f["pu"]), st_cell),
            Paragraph(_fmt(f["importe"]), st_cellb),
        ])

    col_w = [24 * mm, 78 * mm, 15 * mm, 24 * mm, 26 * mm]
    tbl = Table(data, colWidths=col_w, repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAV),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, SOFT]),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
        ("ALIGN", (2, 0), (4, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    # Header en blanco tambien para las celdas Paragraph
    data[0] = [Paragraph(f'<font color="white"><b>{h}</b></font>', st_cell) for h in head]
    story.append(tbl)
    story.append(Spacer(1, 10))

    # Totales (alineados a la derecha)
    piezas = sum(int(f["cant"]) for f in filas)
    tot = Table(
        [[Paragraph("Piezas", st_cell), Paragraph(str(piezas), st_cellb)],
         [Paragraph("Subtotal", st_cell), Paragraph(_fmt(subtotal), st_cellb)],
         [Paragraph("<b>Total (sin IVA)</b>", st_cellb), Paragraph(f"<b>{_fmt(total)}</b>", st_cellb)]],
        colWidths=[40 * mm, 34 * mm],
    )
    tot.setStyle(TableStyle([
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("LINEABOVE", (0, 0), (-1, 0), 0.4, LINE),
        ("BACKGROUND", (0, 2), (-1, 2), GREEN_BG),
        ("TEXTCOLOR", (0, 2), (-1, 2), GREEN_TX),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    wrap = Table([[tot]], colWidths=[doc.width])
    wrap.setStyle(TableStyle([("ALIGN", (0, 0), (0, 0), "RIGHT")]))
    story.append(wrap)

    story.append(Spacer(1, 14))
    story.append(Paragraph(
        "Precios tomados de Aspel SAE. Cotización sin IVA. "
        "Sujeta a existencia y a cambios sin previo aviso.", st_foot))

    doc.build(story)
    return buf.getvalue()


def pdf_a_png(pdf_bytes: bytes, escala: float = 2.0) -> bytes | None:
    """Convierte la primera página del PDF a PNG. None si pypdfium2 no está."""
    try:
        import pypdfium2 as pdfium
    except Exception:
        return None
    pdf = pdfium.PdfDocument(pdf_bytes)
    try:
        page = pdf[0]
        bitmap = page.render(scale=escala)
        pil = bitmap.to_pil()
        out = io.BytesIO()
        pil.save(out, format="PNG")
        return out.getvalue()
    finally:
        pdf.close()


if __name__ == "__main__":
    meta = {"cliente": "Joyería Demo", "folio": "COT-001",
            "fecha": "18/09/2026", "lista": "Precio de lista 3"}
    filas = [
        {"clave": "PA01", "descr": "CAJA BLANDA ANILLO GR", "linea": "F",
         "cant": 11, "pu": 60.0, "importe": 660.0},
        {"clave": "CAD01", "descr": "CUBREPOLVO CARTIER", "linea": "A",
         "cant": 5, "pu": 15.0, "importe": 75.0},
    ]
    pdf = construir_pdf(meta, filas, 735.0, 735.0)
    open("_demo_cotizacion.pdf", "wb").write(pdf)
    png = pdf_a_png(pdf)
    if png:
        open("_demo_cotizacion.png", "wb").write(png)
    print(f"PDF {len(pdf)} bytes | PNG {len(png) if png else 'N/A'} bytes")
