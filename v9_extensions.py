"""Version 9 extensions — make the app fully Excel-independent.

Version 8.3 could import and calculate, but several day-to-day tasks still
required editing the Excel workbook and re-importing:

  * setting or changing MRP / selling price for a product-size,
  * editing an existing product (source, default vendor/shipping, misc %),
  * adding or removing a size for an existing product,
  * discontinuing / deleting a product,
  * confirming app costs against the imported workbook.

Version 9 adds those as first-class, audited operations on
``DatabaseCostingEngine`` so the SQLite database can be the single source of
truth. The Excel workbook becomes an optional one-time seed / backup only.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union
import json

from database_engine import (
    DatabaseCostingEngine,
    normalize,
    norm_key,
    serialize,
    finite_number,
)


def _blank(value: Any) -> bool:
    return value is None or normalize(value) == ""


# ------------------------------------------------------------------
# MRP / selling price management
# ------------------------------------------------------------------

def upsert_mrp_variation(
    self: DatabaseCostingEngine,
    item: str,
    size_g: Union[int, float, str],
    mrp: Any,
    final_cost: Any = None,
) -> None:
    """Create or update the MRP / selling price for a product-size.

    Unlike the Version 6 ``update_mrp_variation`` (which required the row to
    already exist), this inserts the row when missing, so a selling price can be
    set for any product-size entirely inside the app.
    """
    self.ensure_v6_schema()
    item = normalize(item)
    if not item:
        raise ValueError("Item cannot be blank")
    size = finite_number(size_g, "Size", minimum=0.000001)
    ikey = norm_key(item)

    mrp_num = None if _blank(mrp) else finite_number(mrp, "MRP", minimum=0)

    existing = self.conn.execute(
        "SELECT item, final_cost, mrp FROM new_cost_variations WHERE item_norm=? AND size_g=?",
        (ikey, size),
    ).fetchone()

    if final_cost is None:
        fc = existing["final_cost"] if existing else None
    else:
        fc = None if _blank(final_cost) else finite_number(final_cost, "Final cost", minimum=0)

    profit = (mrp_num - fc) if (mrp_num is not None and fc is not None) else None
    old_mrp = existing["mrp"] if existing else None
    display_name = existing["item"] if existing else item

    self.conn.execute(
        """
        INSERT OR REPLACE INTO new_cost_variations(item, item_norm, size_g, final_cost, mrp, profit)
        VALUES(?,?,?,?,?,?)
        """,
        (display_name, ikey, size, fc, mrp_num, profit),
    )
    self.conn.commit()
    self.log_change("MRP", f"{display_name} / {int(size)}g", "mrp", old_mrp, mrp_num, "Set selling price / MRP in app.")


def delete_mrp_variation(self: DatabaseCostingEngine, item: str, size_g: Union[int, float, str]) -> None:
    self.ensure_v6_schema()
    size = finite_number(size_g, "Size", minimum=0.000001)
    self.conn.execute(
        "DELETE FROM new_cost_variations WHERE item_norm=? AND size_g=?",
        (norm_key(item), size),
    )
    self.conn.commit()
    self.log_change("MRP", f"{normalize(item)} / {int(size)}g", "delete", "", "", "Removed selling price row.")


def mrp_editor_rows(
    self: DatabaseCostingEngine,
    search: str = "",
    cost_mode: str = "D2C / Retail full cost with courier shipping",
    limit: int = 2000,
) -> List[Dict[str, Any]]:
    """Selling-price rows enriched with the app's live calculated cost + margin.

    This lets pricing be decided inside the app: you see the current cost next
    to the MRP, so the spreadsheet is no longer needed to price a product.
    """
    rows = self.list_mrp_variations(search=search, limit=limit)
    out: List[Dict[str, Any]] = []
    for r in rows:
        live_cost: Optional[float] = None
        margin: Optional[float] = None
        status = "No MRP" if _blank(r.get("mrp")) else ""
        try:
            defaults = self.costing_defaults_for_product(r["item"], r["size_g"])
            result = self.calculate_pricing(
                item=r["item"],
                size_g=r["size_g"],
                source=defaults.get("source"),
                shipping_pack=defaults.get("shipping_pack"),
                sale_type=defaults.get("sale_type") or "Wholesale",
                vendor=defaults.get("vendor") or "Maruthi Plastics",
                cost_mode=cost_mode,
            )
            live_cost = round(float(result.selected_cost), 2)
            if r.get("mrp"):
                margin = (float(r["mrp"]) - live_cost) / float(r["mrp"])
                status = result.status
        except Exception:
            if not status:
                status = "Setup Incomplete"
        out.append(
            {
                "item_norm": r["item_norm"],
                "Item": r["item"],
                "Size (g)": r["size_g"],
                "Live Cost": live_cost,
                "MRP": r.get("mrp"),
                "Margin %": margin,
                "Status": status,
            }
        )
    return out


# ------------------------------------------------------------------
# Product lifecycle: edit, add/remove sizes, delete
# ------------------------------------------------------------------

def list_products_admin(self: DatabaseCostingEngine, search: str = "", limit: int = 2000) -> List[Dict[str, Any]]:
    self.ensure_v6_schema()
    where = "WHERE item IS NOT NULL AND item_norm <> ''"
    params: List[Any] = []
    if normalize(search):
        where += " AND item_norm LIKE ?"
        params.append(f"%{norm_key(search)}%")
    params.append(int(limit))
    rows = self.conn.execute(
        f"""
        SELECT item_norm, MIN(item) AS item, MIN(source) AS source, MIN(vendor) AS vendor,
               MIN(shipping_pack) AS shipping_pack, MIN(row_no) AS first_row
        FROM production_rows
        {where}
        GROUP BY item_norm
        ORDER BY MIN(row_no)
        LIMIT ?
        """,
        tuple(params),
    ).fetchall()
    out: List[Dict[str, Any]] = []
    for r in rows:
        ikey = r["item_norm"]
        size_rows = self.conn.execute(
            "SELECT DISTINCT size_g FROM production_rows WHERE item_norm=? AND size_g IS NOT NULL ORDER BY size_g",
            (ikey,),
        ).fetchall()
        sizes = ", ".join(str(int(s["size_g"])) for s in size_rows)
        cat = self.conn.execute(
            "SELECT category, gst_pct FROM item_catalog WHERE item_norm=?", (ikey,)
        ).fetchone()
        recipe = self.conn.execute(
            "SELECT 1 FROM recipe_headers WHERE product_norm=? AND active=1", (ikey,)
        ).fetchone()
        mrp_count = self.conn.execute(
            "SELECT COUNT(*) AS n FROM new_cost_variations WHERE item_norm=? AND mrp IS NOT NULL AND mrp>0",
            (ikey,),
        ).fetchone()["n"]
        out.append(
            {
                "item_norm": ikey,
                "Product": r["item"],
                "Category": cat["category"] if cat else None,
                "Source / Type": r["source"],
                "GST %": cat["gst_pct"] if cat else None,
                "Sizes (g)": sizes,
                "Has Recipe": bool(recipe),
                "Priced Sizes": int(mrp_count),
            }
        )
    return out


def update_product_core(
    self: DatabaseCostingEngine,
    item_norm: str,
    *,
    category: Optional[str] = None,
    source_or_type: Optional[str] = None,
    gst_pct: Any = None,
    default_vendor: Optional[str] = None,
    default_shipping_pack: Optional[str] = None,
    sale_type: Optional[str] = None,
    misc_pct: Any = None,
) -> None:
    """Edit core attributes of an existing product across all backing tables."""
    self.ensure_v6_schema()
    cat_row = self.conn.execute(
        "SELECT item_name, category, gst_pct, active FROM item_catalog WHERE item_norm=?",
        (item_norm,),
    ).fetchone()
    name = cat_row["item_name"] if cat_row else item_norm

    # item_catalog: category + GST (audited via update_item_catalog_row).
    if cat_row and (category is not None or gst_pct is not None):
        self.update_item_catalog_row(
            item_norm,
            category if category is not None else cat_row["category"],
            gst_pct if gst_pct is not None else cat_row["gst_pct"],
            bool(cat_row["active"]),
        )

    # Source / type: catalog, master VLOOKUP column 2, and production rows.
    if source_or_type is not None:
        self.conn.execute(
            "UPDATE item_catalog SET source_or_type=? WHERE item_norm=?", (source_or_type, item_norm)
        )
        vrow = self.conn.execute(
            "SELECT row_no FROM master_vlookup WHERE row_key_norm=? ORDER BY row_no LIMIT 1", (item_norm,)
        ).fetchone()
        if vrow is not None:
            self.update_master_value_by_row(int(vrow["row_no"]), 2, source_or_type)
        self.conn.execute(
            "UPDATE production_rows SET source=? WHERE item_norm=?", (source_or_type, item_norm)
        )

    # production_rows defaults.
    sets: List[str] = []
    vals: List[Any] = []
    if default_vendor is not None:
        sets.append("vendor=?")
        vals.append(default_vendor)
    if default_shipping_pack is not None:
        sets.append("shipping_pack=?")
        vals.append(default_shipping_pack)
    if sale_type is not None:
        sets.append("sale_type=?")
        vals.append(sale_type)
    if misc_pct is not None and not _blank(misc_pct):
        sets.append("misc_pct=?")
        vals.append(finite_number(misc_pct, "Miscellaneous %", minimum=0, maximum=100))
    if sets:
        vals.append(item_norm)
        self.conn.execute(
            f"UPDATE production_rows SET {', '.join(sets)} WHERE item_norm=?", tuple(vals)
        )

    self.conn.commit()
    self.log_change("Product", name, "edit", "", "Edited product attributes.", "Product attributes updated in app.")


def _matrix_col_meta(self: DatabaseCostingEngine, table: str, size: float):
    row = self.conn.execute(
        "SELECT col_no, col_key, col_key_norm, col_key_num FROM matrix_values WHERE table_name=? AND col_key_num=? LIMIT 1",
        (table, size),
    ).fetchone()
    return dict(row) if row else None


def add_product_size(
    self: DatabaseCostingEngine,
    item: str,
    size_g: Union[int, float, str],
    *,
    vendor: str = "Maruthi Plastics",
    shipping_pack: str = "Five Ply Box",
    sale_type: str = "Wholesale",
    packaging_material: str = "",
    packing_required_qty: Any = 1,
    source_or_type: Optional[str] = None,
) -> None:
    """Add a new size variation to an existing product."""
    self.ensure_v6_schema()
    item = normalize(item)
    ikey = norm_key(item)
    size = finite_number(size_g, "Size", minimum=0.000001)
    packing_qty = finite_number(packing_required_qty or 0, "Packing quantity", minimum=0)

    existing = self.conn.execute(
        "SELECT 1 FROM production_rows WHERE item_norm=? AND size_g=?", (ikey, size)
    ).fetchone()
    if existing:
        raise ValueError(f"{item} already has a {int(size)}g variation")

    if source_or_type is None:
        src_row = self.conn.execute(
            "SELECT source FROM production_rows WHERE item_norm=? AND source IS NOT NULL ORDER BY row_no LIMIT 1",
            (ikey,),
        ).fetchone()
        source_or_type = src_row["source"] if src_row else ""

    next_row = int(self.conn.execute("SELECT COALESCE(MAX(row_no),2)+1 AS n FROM production_rows").fetchone()["n"])
    self.conn.execute(
        """
        INSERT OR IGNORE INTO production_rows(row_no,item,item_norm,source,shipping_pack,size_g,sale_type,vendor,expected_total_cost)
        VALUES(?,?,?,?,?,?,?,?,NULL)
        """,
        (next_row, item, ikey, source_or_type, shipping_pack, size, sale_type, vendor),
    )
    self.conn.execute(
        "INSERT OR IGNORE INTO new_cost_variations(item,item_norm,size_g,final_cost,mrp,profit) VALUES(?,?,?,NULL,NULL,NULL)",
        (item, ikey, size),
    )

    def insert_matrix(table: str, value: Any) -> None:
        meta = _matrix_col_meta(self, table, size)
        if not meta:
            return
        existing_row = self.conn.execute(
            "SELECT row_no FROM matrix_values WHERE table_name=? AND row_key_norm=? LIMIT 1", (table, ikey)
        ).fetchone()
        if existing_row:
            row_no = int(existing_row["row_no"])
        else:
            row_no = int(
                self.conn.execute(
                    "SELECT COALESCE(MAX(row_no),0)+1 AS n FROM matrix_values WHERE table_name=?", (table,)
                ).fetchone()["n"]
            )
        text, num, kind = serialize(value)
        self.conn.execute(
            """
            INSERT OR REPLACE INTO matrix_values(table_name,row_no,col_no,row_key,row_key_norm,col_key,col_key_norm,col_key_num,value_text,value_num,value_kind)
            VALUES(?,?,?,?,?,?,?,?,?,?,?)
            """,
            (table, row_no, int(meta["col_no"]), item, ikey, meta["col_key"], meta["col_key_norm"], meta["col_key_num"], text, num, kind),
        )

    insert_matrix("packing_required", packing_qty)
    insert_matrix("maruthi_packaging", packaging_material if normalize(vendor) == "Maruthi Plastics" else "")
    insert_matrix("swiss_packaging", packaging_material if normalize(vendor) == "Swiss Pac" else "")

    self.conn.commit()
    self.log_change("Product", item, "add_size", "", f"{int(size)}g", "Added a size variation in app.")


def remove_product_size(self: DatabaseCostingEngine, item: str, size_g: Union[int, float, str]) -> None:
    self.ensure_v6_schema()
    ikey = norm_key(item)
    size = finite_number(size_g, "Size", minimum=0.000001)
    self.conn.execute("DELETE FROM production_rows WHERE item_norm=? AND size_g=?", (ikey, size))
    self.conn.execute("DELETE FROM new_cost_variations WHERE item_norm=? AND size_g=?", (ikey, size))
    for table in ("packing_required", "maruthi_packaging", "swiss_packaging"):
        self.conn.execute(
            "DELETE FROM matrix_values WHERE table_name=? AND row_key_norm=? AND col_key_num=?",
            (table, ikey, size),
        )
    self.conn.commit()
    self.log_change("Product", normalize(item), "remove_size", f"{int(size)}g", "", "Removed a size variation in app.")


def delete_product(self: DatabaseCostingEngine, item: str) -> None:
    """Permanently remove a product and all of its data from the app database."""
    self.ensure_v6_schema()
    ikey = norm_key(item)
    name_row = self.conn.execute(
        "SELECT MIN(item) AS item FROM production_rows WHERE item_norm=?", (ikey,)
    ).fetchone()
    name = (name_row["item"] if name_row and name_row["item"] else normalize(item))

    self.conn.execute("DELETE FROM production_rows WHERE item_norm=?", (ikey,))
    self.conn.execute("DELETE FROM new_cost_variations WHERE item_norm=?", (ikey,))
    self.conn.execute("DELETE FROM in_house_rates WHERE item_norm=?", (ikey,))
    for table in ("packing_required", "maruthi_packaging", "swiss_packaging"):
        self.conn.execute("DELETE FROM matrix_values WHERE table_name=? AND row_key_norm=?", (table, ikey))
    self.conn.execute("DELETE FROM recipe_ingredients WHERE product_norm=?", (ikey,))
    self.conn.execute("DELETE FROM recipe_headers WHERE product_norm=?", (ikey,))
    self.conn.execute("DELETE FROM raw_material_sources WHERE material_norm=?", (ikey,))
    self.conn.execute("DELETE FROM item_catalog WHERE item_norm=?", (ikey,))
    self.conn.execute("DELETE FROM master_vlookup WHERE row_key_norm=?", (ikey,))
    self.conn.commit()
    self.log_change("Product", name, "delete", "", "", "Deleted product and all related rows in app.")


# ------------------------------------------------------------------
# Cost reconciliation: app formula vs imported workbook values
# ------------------------------------------------------------------

def cost_reconciliation_rows(self: DatabaseCostingEngine, tolerance: float = 0.01) -> List[Dict[str, Any]]:
    """Compare the app's calculated cost to the imported workbook cost per row.

    Helps verify trust in the app before retiring the spreadsheet. The app uses
    the consistent Version 8.3 formula; rows that differ are flagged with the
    rupee gap so they can be reviewed deliberately, not silently.
    """
    out: List[Dict[str, Any]] = []
    rows = self.conn.execute(
        """
        SELECT row_no, item, size_g, sale_type, vendor, source, shipping_pack,
               expected_total_cost, expected_wholesale_cost
        FROM production_rows
        WHERE expected_total_cost IS NOT NULL OR expected_wholesale_cost IS NOT NULL
        ORDER BY row_no
        """
    ).fetchall()
    for r in rows:
        record: Dict[str, Any] = {
            "Item": r["item"],
            "Size (g)": int(r["size_g"]) if r["size_g"] is not None else None,
        }
        for mode, exp_key, label in (
            ("D2C / Retail full cost with courier shipping", "expected_total_cost", "Full"),
            ("Wholesale cost excluding courier shipping", "expected_wholesale_cost", "Wholesale"),
        ):
            expected = r[exp_key]
            if expected is None:
                record[f"App {label}"] = None
                record[f"Excel {label}"] = None
                record[f"Diff {label}"] = None
                continue
            try:
                res = self.calculate_pricing(
                    item=r["item"],
                    size_g=r["size_g"],
                    sale_type=r["sale_type"] or "Wholesale",
                    vendor=r["vendor"] or "Maruthi Plastics",
                    shipping_pack=r["shipping_pack"],
                    source=r["source"],
                    cost_mode=mode,
                )
                app_cost = round(float(res.selected_cost), 2)
                record[f"App {label}"] = app_cost
                record[f"Excel {label}"] = round(float(expected), 2)
                record[f"Diff {label}"] = round(app_cost - float(expected), 2)
            except Exception as exc:
                record[f"App {label}"] = None
                record[f"Excel {label}"] = round(float(expected), 2)
                record[f"Diff {label}"] = None
                record.setdefault("Note", str(exc))
        diffs = [record.get("Diff Full"), record.get("Diff Wholesale")]
        record["Matches"] = all(d is None or abs(d) < tolerance for d in diffs)
        out.append(record)
    return out


# ------------------------------------------------------------------
# Attach to the engine
# ------------------------------------------------------------------

for _name, _fn in {
    "upsert_mrp_variation": upsert_mrp_variation,
    "delete_mrp_variation": delete_mrp_variation,
    "mrp_editor_rows": mrp_editor_rows,
    "list_products_admin": list_products_admin,
    "update_product_core": update_product_core,
    "add_product_size": add_product_size,
    "remove_product_size": remove_product_size,
    "delete_product": delete_product,
    "cost_reconciliation_rows": cost_reconciliation_rows,
}.items():
    setattr(DatabaseCostingEngine, _name, _fn)


# Bump the reported app version.
_old_database_check_v9_base = DatabaseCostingEngine.database_check


def _database_check_v9(self) -> Dict[str, Any]:
    base = _old_database_check_v9_base(self)
    base.setdefault("meta", {})["app_version"] = "9.0"
    return base


DatabaseCostingEngine.database_check = _database_check_v9
