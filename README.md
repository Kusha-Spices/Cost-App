# Kusha Spices Costing App — Version 8.3

A local internal costing app for Kusha Spices built with Streamlit, Python and SQLite.

## What Version 8.3 includes

- Calculator with D2C/retail full cost and wholesale cost excluding courier shipping
- MRP, profit, margin and status
- Portfolio reports
- Editable master data foundation
- Packaging mapping editor
- Item-level GST and transport source editor
- BOM / recipe builder for masalas and blends
- Automatic import of all 27 recipe blocks from the Master Data sheet
- Recipe-level energy/miscellaneous overhead and an approval switch before recipes affect live costing
- Warning for recipe quantities that do not total 1,000g
- Audit log and validation center
- Database backup / restore
- Clean Excel export from current database
- Wholesale cost mode excluding courier/new shipping
- Updated Master Data/Production Cost ranges from the latest workbook
- Mac and Windows one-click launchers
- Live portfolio reports recalculated from current SQLite master data
- Finite/non-negative input validation and recipe-total validation
- Clean workbook rebuilds without stale product or recipe rows
- Stress test covering all cost-ready production rows, persistence, export and concurrent calculations

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

### Mac

```bash
cd kusha_costing_app_v8_3
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python self_check.py
streamlit run app.py
```

### Windows

```powershell
cd kusha_costing_app_v8
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python self_check.py
streamlit run app.py
```

## Note on installation

This package includes one-click launchers, not a signed standalone installer. For a real `.app` or `.exe`, a developer should package the project on the target OS using PyInstaller, Briefcase, Electron, or move it to a hosted production web stack.
