"""Version 10 — data organisation & presentation helpers.

This module follows the same pattern as the other ``vN_extensions`` files: it
monkey-patches a few read/maintenance methods onto ``DatabaseCostingEngine`` so
the UI can present the data in a cleaner, more organised way **without changing
the costing logic or the database schema**.

Two user-visible improvements live here:

* ``tidy_item_catalog`` — the item catalogue was seeded from a raw Excel dump and
  contains ~20 spreadsheet scaffolding rows ("Index", "RAW MATERIALS COST",
  "Labour_Cost_Working", …) plus dozens of real ingredients that were never
  categorised. This safely deactivates the non-product rows and files the known
  ingredients under "Raw Material". It only touches ``item_catalog.active`` and
  ``item_catalog.category`` (which drive the catalogue view and ingredient
  dropdowns, NOT the core cost calculation), every change is audited, and it is
  fully reversible.
* ``data_overview`` — a grouped, plain-language summary of what data lives where,
  used to replace raw table-count dumps with something a non-technical user can
  read.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

from database_engine import DatabaseCostingEngine
from v5_extensions import ensure_v5_schema

# Category used to park rows that are not real products (spreadsheet headers,
# calculation scaffolding, etc.). Rows in this category are hidden from the
# catalogue by default.
SYSTEM_CATEGORY = "System / Not a Product"

# Exact lower-cased names known to be Excel section headers / scaffolding.
_JUNK_EXACT = {
    "index", "pm required", "pm specifications", "name of the item",
    "vendor transport costs", "vendor transport cost calculation",
    "raw materials source costs", "drop down validation master",
    "raw materials cost", "raw material cost", "labour cost",
    "labour cost working", "packaging cost", "total", "header", "particulars",
}


def is_catalog_junk(name: Any) -> bool:
    """True when an item-catalogue name is clearly spreadsheet scaffolding, not a
    real product. Deliberately conservative: real spice/product names use spaces
    and brackets, never underscores, are not purely numeric, and are not written
    in ALL CAPS."""
    if name is None:
        return True
    s = str(name).strip()
    if not s:
        return True
    low = s.lower()
    if low in _JUNK_EXACT:
        return True
    if "_" in s:                                   # Raw_Material_Cost, Labour_Cost_Working
        return True
    if re.fullmatch(r"[0-9]+(\.[0-9]+)?", s):      # '2'
        return True
    if s.isupper() and len(s) > 3:                 # 'RAW MATERIALS COST'
        return True
    return False


def catalog_cleanup_preview(self: DatabaseCostingEngine) -> Dict[str, Any]:
    """Dry-run: report what ``tidy_item_catalog`` would change, without writing."""
    return tidy_item_catalog(self, apply=False)


def tidy_item_catalog(self: DatabaseCostingEngine, apply: bool = True) -> Dict[str, Any]:
    """Deactivate non-product scaffolding rows and categorise known ingredients.

    Returns a summary dict with the names affected. Set ``apply=False`` for a
    preview. All edits are reversible (they only flip ``active`` / ``category``)
    and recorded in the audit log when available.
    """
    ensure_v5_schema(self)

    rows = self.conn.execute(
        "SELECT item_norm, item_name, category, active FROM item_catalog"
    ).fetchall()

    def _norm_set(sql: str) -> set:
        try:
            return {r[0] for r in self.conn.execute(sql).fetchall() if r[0]}
        except Exception:
            return set()

    known_ingredients = (
        _norm_set("SELECT DISTINCT ingredient_norm FROM recipe_ingredients")
        | _norm_set("SELECT DISTINCT material_norm FROM raw_material_sources")
        | _norm_set("SELECT DISTINCT item_norm FROM production_rows")
    )

    deactivated: List[str] = []
    recategorized: List[str] = []

    for r in rows:
        name = r["item_name"]
        norm = r["item_norm"]
        category = r["category"]
        active = r["active"]

        if is_catalog_junk(name):
            if active or category != SYSTEM_CATEGORY:
                deactivated.append(str(name))
                if apply:
                    self.conn.execute(
                        "UPDATE item_catalog SET active=0, category=? WHERE item_norm=?",
                        (SYSTEM_CATEGORY, norm),
                    )
                    if hasattr(self, "log_change"):
                        self.log_change(
                            "Catalog Tidy", str(name), "active/category",
                            f"{active} / {category}", f"0 / {SYSTEM_CATEGORY}",
                            "Auto-hidden: not a real product (spreadsheet scaffolding).",
                        )
        elif category == "Other / Review" and norm in known_ingredients:
            recategorized.append(str(name))
            if apply:
                self.conn.execute(
                    "UPDATE item_catalog SET category='Raw Material' WHERE item_norm=?",
                    (norm,),
                )
                if hasattr(self, "log_change"):
                    self.log_change(
                        "Catalog Tidy", str(name), "category",
                        category, "Raw Material",
                        "Auto-categorised: used as a raw material / ingredient.",
                    )

    if apply:
        self.conn.commit()

    return {
        "deactivated": deactivated,
        "recategorized": recategorized,
        "deactivated_count": len(deactivated),
        "recategorized_count": len(recategorized),
    }


def data_overview(self: DatabaseCostingEngine) -> List[Dict[str, Any]]:
    """Grouped, plain-language summary of the app's data for the Data Overview
    panel — far friendlier than a raw per-table row count."""

    def cnt(sql: str) -> int:
        try:
            return int(self.conn.execute(sql).fetchone()[0])
        except Exception:
            return 0

    return [
        {"Area": "📦 Products", "Records": cnt("SELECT COUNT(DISTINCT item_norm) FROM production_rows"),
         "What it holds": "Sellable products and their size variations.",
         "Where to manage it": "Calculator · Admin → Manage Products"},
        {"Area": "💰 Prices (MRP)", "Records": cnt("SELECT COUNT(*) FROM new_cost_variations"),
         "What it holds": "Selling price for each product + size, beside live cost & margin.",
         "Where to manage it": "Master Data → MRP & Selling Price"},
        {"Area": "🧪 Recipes (BOM)", "Records": cnt("SELECT COUNT(*) FROM recipe_headers"),
         "What it holds": "Masala / blend recipes standardised per 1 kg.",
         "Where to manage it": "Recipes"},
        {"Area": "🌿 Raw materials & transport", "Records": cnt("SELECT COUNT(*) FROM raw_material_sources"),
         "What it holds": "Vendor/source costs with transport legs and GST.",
         "Where to manage it": "Transport & GST"},
        {"Area": "🛍️ Packaging", "Records": cnt("SELECT COUNT(*) FROM packaging_materials"),
         "What it holds": "Packaging materials and which one each product-size uses.",
         "Where to manage it": "Master Data → Packaging List / Mapping"},
        {"Area": "🚚 Shipping zones", "Records": cnt("SELECT COUNT(*) FROM shipping_zone_weights"),
         "What it holds": "Courier zone costs and order-mix weighting.",
         "Where to manage it": "Master Data → Shipping Logic"},
        {"Area": "🏷️ Item catalog & GST", "Records": cnt(
            f"SELECT COUNT(*) FROM item_catalog WHERE active=1 AND category != '{SYSTEM_CATEGORY}'"),
         "What it holds": "Master list of items with category and item-level GST.",
         "Where to manage it": "Master Data → Items & Rates"},
        {"Area": "🕮 Change history", "Records": cnt("SELECT COUNT(*) FROM audit_log"),
         "What it holds": "Every edit you make, with old → new values.",
         "Where to manage it": "Admin → Audit Log"},
    ]


DatabaseCostingEngine.is_catalog_junk = staticmethod(is_catalog_junk)
DatabaseCostingEngine.tidy_item_catalog = tidy_item_catalog
DatabaseCostingEngine.catalog_cleanup_preview = catalog_cleanup_preview
DatabaseCostingEngine.data_overview = data_overview
