# Kusha Spices Costing App — Version 9.0

A local internal costing app for Kusha Spices built with Streamlit, Python and SQLite.

**Version 9.0 makes the app Excel-free.** The local SQLite database is the single
source of truth. The Excel workbook is now optional — used only to seed a brand-new
database or as a backup/export format. Every task that previously required editing the
spreadsheet can now be done inside the app.

## What you can do entirely in the app (no spreadsheet)

- **Calculate cost** in two modes: D2C/retail full cost (with courier) and wholesale cost (excluding courier), with MRP, profit, margin and a Good/Low-Margin/Loss verdict.
- **Set and edit MRP / selling prices** for every product-size, shown next to the live recalculated cost (Master Data Center → *MRP & Selling Price*).
- **Create, edit, resize and discontinue products** — change source, vendor, shipping pack, miscellaneous %, GST and category; add or remove sizes; delete a product (Admin Controls → *Manage Products*).
- **Edit raw/product rates, item-level GST, packaging lists, packaging mappings, shipping logic and storage/labour/sticker settings.**
- **Build BOM / recipes** for masalas and blends — all 27 recipe blocks are imported from the Master Data sheet, with energy/miscellaneous overhead and an approval switch before a recipe affects live costing (recipes must total 1,000g).
- **Maintain raw-material source and transport costing** with item-level GST.
- **Reconcile** app costs against the original workbook (Database Check → *Cost reconciliation*).
- **Portfolio reports**, validation center, full audit log, database backup/restore and clean Excel export.

## Engineering safeguards

- Finite/non-negative input validation and recipe-total validation.
- Every edit is captured in the audit log.
- Clean rebuilds from Excel never retain stale app-created rows.
- `self_check.py` and `stress_test.py` cover import integrity, all cost-ready production rows, Excel-free MRP/product management, persistence, export and 4,800 concurrent calculations.

## Data model in brief

The Excel workbook is imported into SQLite once; the app then reads and writes SQLite:

```
Cost Sheet ….xlsx ──one-time import──▶ data/kusha_costing_v8.3.sqlite ──read/write──▶ app
```

Key tables: `production_rows` (product list + defaults), `new_cost_variations`
(MRP/cost/profit per item-size), `master_vlookup` (raw rates/GST), `matrix_values`
(packaging mapping + packing qty), `recipe_headers`/`recipe_ingredients` (BOM),
`raw_material_sources` (transport), `item_catalog`, `audit_log`.

## Fastest way to run

### Mac
Double-click:

`Run_Kusha_Costing_App.command`

If blocked by macOS, right-click → Open.

### Windows
Double-click:

`Run_Kusha_Costing_App_Windows.bat`

Python 3 must be installed first and added to PATH.

## Terminal run

### Mac / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python self_check.py
streamlit run app.py
```

### Windows

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python self_check.py
streamlit run app.py
```

The app opens in your browser. Edits you make are saved to
`data/kusha_costing_v8.3.sqlite`, which persists between runs.

## Note on installation

This package includes one-click launchers, not a signed standalone installer. For a real `.app` or `.exe`, a developer should package the project on the target OS using PyInstaller, Briefcase, Electron, or move it to a hosted production web stack.
