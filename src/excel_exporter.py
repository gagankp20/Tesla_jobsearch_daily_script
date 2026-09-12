"""Excel workbook writer."""
from __future__ import annotations

from pathlib import Path
from typing import Mapping, Sequence

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill

HEADERS = ["Date Discovered", "Posted Date", "Job Title", "Location", "Category", "Employment Type", "Req ID", "Tesla Job URL", "Apply?"]


def _date_only(value: object) -> str:
    """Display legacy timestamps and new discovery dates consistently."""
    return str(value)[:10]


def _write_sheet(workbook: Workbook, title: str, rows: Sequence[Mapping[str, object]], apply_values: Mapping[str, object] | None = None) -> None:
    if title in workbook.sheetnames:
        del workbook[title]
    ws = workbook.create_sheet(title)
    ws.append(HEADERS)
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="B22222")
    for row in rows:
        ws.append([_date_only(row["first_seen_at"]), row["posted_at"], row["title"], row["location"], row["category"],
                   row["employment_type"], row["job_id"], row["url"], (apply_values or {}).get(str(row["job_id"]), "")])
        link_cell = ws.cell(ws.max_row, 8)
        link_cell.hyperlink = str(row["url"])
        link_cell.style = "Hyperlink"
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    for column, width in {"A": 23, "B": 23, "C": 48, "D": 32, "E": 28, "F": 18, "G": 14, "H": 70, "I": 14}.items():
        ws.column_dimensions[column].width = width


def export_workbook(path: Path, new_rows: Sequence[Mapping[str, object]], all_rows: Sequence[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook = load_workbook(path) if path.exists() else Workbook()
    if "Sheet" in workbook.sheetnames and len(workbook.sheetnames) == 1:
        del workbook["Sheet"]
    existing_apply: dict[str, object] = {}
    if "New Jobs" in workbook.sheetnames:
        old_sheet = workbook["New Jobs"]
        for row in old_sheet.iter_rows(min_row=2, values_only=True):
            if len(row) >= 9 and row[6] is not None:
                existing_apply[str(row[6])] = row[8]
    _write_sheet(workbook, "New Jobs", new_rows, existing_apply)
    _write_sheet(workbook, "All Jobs", all_rows)
    workbook.save(path)
