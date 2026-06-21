# Changelog

## Version 9.2 — Friendlier UI, guided help, tidier data & Windows app

Goal: make the app approachable for anyone, organise the data, and ship a native
Windows build alongside macOS.

### Added
- **📘 Start Here guide tab** — a built-in walkthrough: an "I want to… → go here"
  map, a plain-English description of every section, a glossary, a first-time
  checklist and an FAQ. New users can find anything without training.
- **🔎 Data & Checks** — a plain-language **Data Overview** (Products, Prices,
  Recipes, Raw materials, Packaging…) replacing the raw table-count dump, plus a
  one-click **Tidy catalogue** tool.
- **Catalogue tidy** (`v10_extensions.py`): safely hides ~21 leftover spreadsheet
  scaffolding rows (`Index`, `RAW MATERIALS COST`, `Labour_Cost_Working`…) and
  re-files known ingredients out of *Other / Review* into *Raw Material*. Fully
  reversible and audit-logged; never touches the costing logic.
- **Windows app** — `build-windows-app.yml` produces a self-contained
  `KushaCostingApp.exe` (PyInstaller + pywebview/pythonnet), gated by the same
  on-machine `--self-test`, and publishes `Kusha-Costing-App-windows.zip` to the
  release next to the macOS builds.

### Changed
- **UI overhaul**: warm "spice" theme, a branded header, and icon-labelled tabs
  in a logical order (Start Here · Calculator · Reports · Master Data · Recipes ·
  Transport & GST · Admin · Validation · Export · Data & Checks).
- **Cleaner data presentation**: internal join columns (`item_norm`, `row_no`,
  `col_no`, `source_row_no`, `id`) are hidden from every grid; the Items & Rates
  list hides spreadsheet/inactive rows by default; Excel cell codes (`AB32`,
  `V127`) moved out of labels into help text.

## Version 9.0 — Excel-free workflow

Goal: every task that previously required editing the Excel workbook can now be
done inside the app, so the SQLite database is the single source of truth.

### Added
- **MRP & Selling Price editor** (Master Data Center → *MRP & Selling Price*).
  Set or change the selling price for any product-size, with the app's live
  recalculated cost and margin shown alongside so you can price without a
  spreadsheet. Backed by a new `upsert_mrp_variation` that inserts rows when
  missing (the v6 `update_mrp_variation` could only update existing rows).
- **Manage Products** (Admin Controls → *Manage Products*). Edit an existing
  product's source/type, category, GST, default vendor, default shipping pack,
  default type and miscellaneous %; add or remove a size; and permanently
  delete/discontinue a product across every backing table.
- **Cost reconciliation** (Database Check → *Cost reconciliation*). Compares the
  app's calculated cost to the cost stored in the original workbook, per product,
  so the numbers can be trusted before the spreadsheet is retired.
- New engine module `v9_extensions.py` with `upsert_mrp_variation`,
  `delete_mrp_variation`, `mrp_editor_rows`, `list_products_admin`,
  `update_product_core`, `add_product_size`, `remove_product_size`,
  `delete_product` and `cost_reconciliation_rows` — all audit-logged.

### Changed
- The destructive "Rebuild database from bundled Excel" action is now behind an
  expander with an explicit confirmation, because it discards in-app edits.
- App version label is now 9.0; Excel is documented as an optional seed/backup.
- `self_check.py` now also verifies the Excel-free MRP and product-management
  paths end to end.

### Note on the app-vs-Excel cost difference (by design)
The cost reconciliation shows ~51 of the cost-ready 1000g rows differing from the
original workbook by a small, systematic amount (around ₹6–₹15). This is **not a
regression** — it is the Version 8.3 costing formula the package intentionally
standardized on: at 1000g the app includes `storage_cost` inside the overhead
base, which the source spreadsheet handled slightly differently. The app value is
internally consistent and is the intended source of truth going forward. If you
would instead prefer the app to reproduce the spreadsheet's exact 1000g figures,
that is a one-line change to the costing formula and can be added as a setting.

### Verification
- `python self_check.py` → "All Version 9.0 checks passed."
- `python stress_test.py` → `STATUS: PASS` (import integrity, 27 recipes, 104
  cost-ready calculations, invalid-input rejection, edit persistence + audit,
  clean rebuild, Excel export, 4,800 concurrent calculations).
- Streamlit `AppTest` smoke run → 0 application exceptions across all tabs.
