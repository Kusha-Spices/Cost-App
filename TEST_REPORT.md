# Kusha Costing App v8.3 — BOM Recipe Fix

## Outcome

- Imported 27 masala/blend recipe blocks and 346 ingredient rows from the `Master Data` sheet.
- The BOM screen now opens with an actual recipe list instead of the full finished-product list.
- Selecting a recipe automatically displays its ingredients, quantities, 1kg total, recipe overhead and calculated ingredient cost.
- Imported recipes are reference-only by default and cannot silently replace the approved in-house product rate.
- A recipe affects calculator costing only after `Use this verified recipe in calculator costing` is selected and the recipe is saved.
- The app requires a saved recipe to total 1,000g.

## Source-data warning

Twenty-six imported recipes total 1,000g. `Chilli Oil Spice Blend C Revised` totals only 546.675g in the source workbook even though the workbook subtotal states 1,000g. The app preserves the source quantities, shows a warning, and prevents the incomplete recipe from being enabled without correction.

## Verification completed

- Python syntax and module import checks: passed
- SQLite integrity and clean workbook rebuild: passed
- Recipe import count and selected recipe totals: passed
- 104 cost-ready production-row calculations: passed
- Invalid-input and persistence checks: passed
- Audit logging and Excel database export: passed
- 4,800 concurrent calculations across 12 workers: passed
- Streamlit application test: no application exceptions
- BOM screen test: 27 recipe options; Premium Biryani Masala displayed at 1,000g with 10% recipe overhead

## Remaining workbook gaps (not caused by this fix)

- No recipe block exists for `Haldi Doodh Powder`.
- No verified recipe block matches `Premium Garam Masala`; the workbook contains a separate `Garam Masala` recipe with materially different cost values.
- Several MRP, final-cost and packaging mappings remain blank in the source workbook and continue to appear in the Validation Center.
