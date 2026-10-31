"""Multi-format tabular export without Microsoft Office."""

from __future__ import annotations

import csv
import html
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any
from xml.dom import minidom

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet

from .errors import ValidationError


EXPORT_FORMATS = frozenset(
    {"csv", "xlsx", "pdf", "docx", "xml", "html", "png", "jpeg", "jpg"}
)


def _visible_columns(
    columns: list[str],
    visible: list[str] | None,
) -> list[str]:
    if not visible:
        return columns
    allowed = {str(item) for item in visible}
    picked = [column for column in columns if column in allowed]
    return picked or columns


def _row_values(row: dict[str, Any], columns: list[str]) -> list[str]:
    return [str(row.get(column, "")) for column in columns]


class TableExportEngine:
    """Convert report rows to office-free file formats."""

    def __init__(
        self,
        *,
        title: str,
        columns: list[str],
        rows: list[dict[str, Any]],
        visible_columns: list[str] | None = None,
    ) -> None:
        if not columns:
            raise ValidationError("Export requires at least one column")
        self.title = title.strip() or "Report"
        self.columns = _visible_columns(columns, visible_columns)
        self.rows = rows

    def export(self, destination: Path, file_format: str) -> Path:
        fmt = file_format.strip().lower()
        if fmt == "jpg":
            fmt = "jpeg"
        if fmt not in EXPORT_FORMATS:
            raise ValidationError(
                f"Unsupported export format: {file_format}. "
                f"Use one of {', '.join(sorted(EXPORT_FORMATS))}."
            )
        destination.parent.mkdir(parents=True, exist_ok=True)
        handlers = {
            "csv": self._to_csv,
            "xlsx": self._to_xlsx,
            "pdf": self._to_pdf,
            "docx": self._to_docx,
            "xml": self._to_xml,
            "html": self._to_html,
            "png": lambda path: self._to_image(path, "PNG"),
            "jpeg": lambda path: self._to_image(path, "JPEG"),
        }
        path = destination.with_suffix(f".{fmt if fmt != 'jpeg' else 'jpg'}")
        handlers[fmt](path)
        return path

    def _to_csv(self, path: Path) -> None:
        with path.open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.writer(handle)
            writer.writerow(self.columns)
            for row in self.rows:
                writer.writerow(_row_values(row, self.columns))

    def _to_xlsx(self, path: Path) -> None:
        try:
            from openpyxl import Workbook
        except ImportError as exc:
            raise ValidationError(
                'Install export support: pip install -e ".[export]"'
            ) from exc
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = self.title[:31]
        sheet.append(self.columns)
        for row in self.rows:
            sheet.append(_row_values(row, self.columns))
        workbook.save(path)

    def _to_docx(self, path: Path) -> None:
        try:
            from docx import Document
        except ImportError as exc:
            raise ValidationError(
                'Install export support: pip install -e ".[export]"'
            ) from exc
        document = Document()
        document.add_heading(self.title, level=1)
        table = document.add_table(rows=1, cols=len(self.columns))
        table.style = "Table Grid"
        header_cells = table.rows[0].cells
        for index, column in enumerate(self.columns):
            header_cells[index].text = column
        for row in self.rows:
            cells = table.add_row().cells
            values = _row_values(row, self.columns)
            for index, value in enumerate(values):
                cells[index].text = value
        document.save(path)

    def _to_xml(self, path: Path) -> None:
        root = ET.Element("report", title=self.title)
        for row in self.rows:
            item = ET.SubElement(root, "row")
            for column in self.columns:
                child = ET.SubElement(item, column.replace(" ", "_"))
                child.text = str(row.get(column, ""))
        rough = ET.tostring(root, encoding="unicode")
        pretty = minidom.parseString(rough).toprettyxml(indent="  ")
        path.write_text(pretty, encoding="utf-8")

    def _to_html(self, path: Path) -> None:
        head = "".join(f"<th>{html.escape(column)}</th>" for column in self.columns)
        body_rows = []
        for row in self.rows:
            cells = "".join(
                f"<td>{html.escape(str(row.get(column, '')))}</td>"
                for column in self.columns
            )
            body_rows.append(f"<tr>{cells}</tr>")
        content = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/><title>{html.escape(self.title)}</title>
<style>
body{{font-family:Inter,Segoe UI,sans-serif;background:#f8fafc;color:#0f172a}}
table{{border-collapse:collapse;width:100%}} th,td{{border:1px solid #cbd5e1;padding:4px 6px;font-size:12px}}
th{{background:#e2e8f0;text-align:left}}
</style></head><body>
<h1>{html.escape(self.title)}</h1>
<table><thead><tr>{head}</tr></thead><tbody>
{"".join(body_rows)}
</tbody></table></body></html>"""
        path.write_text(content, encoding="utf-8")

    def _to_pdf(self, path: Path) -> None:
        data: list[list[str]] = [self.columns]
        data.extend(_row_values(row, self.columns) for row in self.rows)
        doc = SimpleDocTemplate(
            str(path),
            pagesize=landscape(A4) if len(self.columns) > 7 else A4,
            leftMargin=10 * mm,
            rightMargin=10 * mm,
            topMargin=10 * mm,
            bottomMargin=10 * mm,
            title=self.title,
        )
        styles = getSampleStyleSheet()
        story = [Paragraph(self.title, styles["Heading2"]), Spacer(1, 6)]
        table = Table(data, repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.black),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        story.append(table)
        doc.build(story)

    def _to_image(self, path: Path, image_format: str) -> None:
        try:
            from PIL import Image, ImageDraw, ImageFont
        except ImportError as exc:
            raise ValidationError(
                'Install export support: pip install -e ".[export]"'
            ) from exc
        font = ImageFont.load_default()
        line_height = 16
        col_width = 140
        width = max(640, col_width * len(self.columns) + 40)
        height = max(200, (len(self.rows) + 3) * line_height + 40)
        image = Image.new("RGB", (width, height), "white")
        draw = ImageDraw.Draw(image)
        y = 10
        draw.text((10, y), self.title, fill="black", font=font)
        y += line_height * 2
        x = 10
        for column in self.columns:
            draw.text((x, y), column[:18], fill="#0f172a", font=font)
            x += col_width
        y += line_height
        for row in self.rows:
            x = 10
            for column in self.columns:
                draw.text((x, y), str(row.get(column, ""))[:22], fill="#334155", font=font)
                x += col_width
            y += line_height
        suffix = ".jpg" if image_format == "JPEG" else ".png"
        save_path = path if path.suffix else path.with_suffix(suffix)
        image.save(save_path, format=image_format)

    def metadata_json(self) -> str:
        payload = {
            "title": self.title,
            "columns": self.columns,
            "row_count": len(self.rows),
        }
        return json.dumps(payload, indent=2)
