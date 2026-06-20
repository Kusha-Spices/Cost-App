from __future__ import annotations

from io import BytesIO
from typing import Any, Dict, List

import pandas as pd

from database_engine import DatabaseCostingEngine
from v5_extensions import ensure_v5_schema
from v6_extensions import ensure_v6_schema


def _table_exists(self: DatabaseCostingEngine, table_name: str) -> bool:
    row = self.conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone()
    return row is not None


def _read_table(self: DatabaseCostingEngine, table_name: str, limit: int | None = None) -> pd.DataFrame:
    if not _table_exists(self, table_name):
        return pd.DataFrame()
    sql = f"SELECT * FROM {table_name}"
    if limit is not None:
        sql += f" LIMIT {int(limit)}"
    return pd.read_sql_query(sql, self.conn)


def _clean_sheet_name(name: str) -> str:
    # Excel sheet names max 31 chars and cannot contain []:*?/\\
    bad = '[]:*?/\\'
    out = ''.join('_' if c in bad else c for c in name)[:31]
    return out or 'Sheet'


def export_database_to_excel_v7(self: DatabaseCostingEngine) -> bytes:
    """Create a clean Excel export from the current SQLite database.

    This is not intended to recreate the original workbook cell-by-cell. It creates a
    structured backup/report workbook that a developer/admin can inspect or share.
    """
    ensure_v5_schema(self)
    ensure_v6_schema(self)

    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Summary / metadata
        try:
            check = self.database_check()
            meta_rows = [{'Key': k, 'Value': v} for k, v in check.get('meta', {}).items()]
            count_rows = [{'Table': k, 'Rows': v} for k, v in check.get('counts', {}).items()]
        except Exception:
            meta_rows, count_rows = [], []
        pd.DataFrame(meta_rows).to_excel(writer, sheet_name='Import Metadata', index=False)
        pd.DataFrame(count_rows).to_excel(writer, sheet_name='Table Counts', index=False)

        # Decision/report sheets
        try:
            report = pd.DataFrame(self.sku_report_from_new_cost())
            if not report.empty:
                report.to_excel(writer, sheet_name='SKU Margin Report', index=False)
                report[report['Status'] == 'Loss'].to_excel(writer, sheet_name='Loss Making SKUs', index=False)
                report[report['Status'] == 'Low Margin'].to_excel(writer, sheet_name='Low Margin SKUs', index=False)
        except Exception:
            pass

        try:
            issues = pd.DataFrame(self.validation_issues())
            issues.to_excel(writer, sheet_name='Validation Issues', index=False)
        except Exception:
            pass

        # Master/admin tables
        table_map = {
            'item_catalog': 'Item Catalog GST',
            'packaging_materials': 'Packaging Materials',
            'raw_material_sources': 'Transport GST Sources',
            'recipe_headers': 'Recipe Headers',
            'recipe_ingredients': 'Recipe Ingredients',
            'shipping_zone_weights': 'Shipping Zone Weights',
            'new_cost_variations': 'MRP Final Cost',
            'production_rows': 'Production Rows',
            'master_vlookup': 'Master VLOOKUP Raw',
            'matrix_values': 'Matrix Values Raw',
            'audit_log': 'Audit Log',
        }
        for table, sheet in table_map.items():
            try:
                df = _read_table(self, table)
                if not df.empty:
                    df.to_excel(writer, sheet_name=_clean_sheet_name(sheet), index=False)
            except Exception:
                # Keep export robust. A missing optional table should not break the download.
                continue

        # Auto-size columns lightly
        for ws in writer.book.worksheets:
            for col in ws.columns:
                max_len = 0
                col_letter = col[0].column_letter
                for cell in col[:200]:
                    try:
                        val = '' if cell.value is None else str(cell.value)
                        max_len = max(max_len, len(val))
                    except Exception:
                        pass
                ws.column_dimensions[col_letter].width = min(max(max_len + 2, 10), 45)

    output.seek(0)
    return output.getvalue()


def installer_notes_v7(self: DatabaseCostingEngine | None = None) -> Dict[str, str]:
    return {
        'mac_quick_launcher': 'Double-click Run_Kusha_Costing_App.command. It creates/uses .venv, installs requirements, and opens Streamlit.',
        'windows_quick_launcher': 'Double-click Run_Kusha_Costing_App_Windows.bat. It creates/uses .venv, installs requirements, and opens Streamlit.',
        'true_desktop_app': 'For a real .app/.exe installer, ask a developer to package with PyInstaller or convert to a FastAPI/React production website.',
    }


for name, fn in {
    'export_database_to_excel_v7': export_database_to_excel_v7,
    'installer_notes_v7': installer_notes_v7,
}.items():
    setattr(DatabaseCostingEngine, name, fn)

# Extend DB check version label.
_old_database_check_v7_base = DatabaseCostingEngine.database_check


def _database_check_v7(self) -> Dict[str, Any]:
    base = _old_database_check_v7_base(self)
    base.setdefault('meta', {})['app_version'] = '8.3'
    return base

DatabaseCostingEngine.database_check = _database_check_v7
