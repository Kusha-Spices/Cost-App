from pathlib import Path
import tempfile
from database_engine import CostingDatabase, DatabaseCostingEngine
import v5_extensions
import v6_extensions
import v7_extensions

DATA_DIR = Path(__file__).parent / "data"
WORKBOOK = DATA_DIR / "Cost Sheet 2026 new(3).xlsx"
print("Building a temporary SQLite database from workbook...")
temp_dir = tempfile.TemporaryDirectory(prefix="kusha_costing_self_check_")
DB_PATH = Path(temp_dir.name) / "kusha_costing_v8.3.sqlite"
db = CostingDatabase(DB_PATH)
db.import_workbook(WORKBOOK)
db.close()

engine = DatabaseCostingEngine(DB_PATH)
engine.ensure_v5_schema()
engine.ensure_v6_schema()

source = engine.source_for_product("Black Cardamom")
pricing_full = engine.calculate_pricing(
    item="Black Cardamom",
    source=source,
    shipping_pack="Recycle Box",
    size_g=1000,
    sale_type="Wholesale",
    vendor="Maruthi Plastics",
    cost_mode="D2C / Retail full cost with courier shipping",
)
pricing_wholesale = engine.calculate_pricing(
    item="Black Cardamom",
    source=source,
    shipping_pack="Recycle Box",
    size_g=1000,
    sale_type="Wholesale",
    vendor="Maruthi Plastics",
    cost_mode="Wholesale cost excluding courier shipping",
)

print("\nBlack Cardamom 1000g Wholesale:")
print(f"Source: {source}")
print(f"Full cost incl. courier: ₹{pricing_full.cost.total_cost_with_new_shipping:,.2f}")
print(f"Wholesale cost excl. courier: ₹{pricing_wholesale.cost.wholesaler_cost_excluding_courier_shipping:,.2f}")
print(f"MRP: ₹{pricing_full.mrp:,.2f}")
print(f"Full mode status: {pricing_full.status}")

assert source == "Ali Kikabai"
assert round(pricing_full.cost.total_cost_with_new_shipping, 2) == 2472.84
assert round(pricing_wholesale.cost.wholesaler_cost_excluding_courier_shipping, 2) == 2404.98
assert round(pricing_full.mrp, 2) == 4299.00
assert pricing_full.status == "Good"

# Confirm duplicate product rule: first Green Cardamom row is used.
green_source = engine.source_for_product("Green Cardamom")
assert green_source == "Nadha Spices"

report_full = engine.sku_report_from_new_cost("D2C / Retail full cost with courier shipping")
report_wholesale = engine.sku_report_from_new_cost("Wholesale cost excluding courier shipping")
print(f"\nFull report rows: {len(report_full)}")
print(f"Wholesale report rows: {len(report_wholesale)}")
assert len(report_full) > 0
assert len(report_wholesale) > 0

check = engine.database_check()
print("\nDatabase counts:")
print(check)
assert check["counts"]["master_vlookup"] > 0
assert check["counts"]["matrix_values"] > 0
assert check["counts"]["production_rows"] > 0
assert check["counts"]["new_cost_variations"] > 0

issues = engine.validation_issues()
print(f"\nValidation issues found: {len(issues)}")
export_bytes = engine.export_database_to_excel_v7()
print(f"\nExcel export bytes: {len(export_bytes):,}")
assert len(export_bytes) > 10000
engine.db.close()
temp_dir.cleanup()
print("All Version 8.3 checks passed.")
