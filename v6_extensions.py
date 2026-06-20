from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
import json

from database_engine import DatabaseCostingEngine, normalize, norm_key, serialize, deserialize, as_number, finite_number


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
    except Exception:
        pass
    return str(value)


def ensure_v6_schema(engine: DatabaseCostingEngine) -> None:
    """Create Version 6 audit/admin tables. Safe to call repeatedly."""
    if getattr(engine, "_v6_schema_ready", False):
        return
    if hasattr(engine, "ensure_v5_schema"):
        engine.ensure_v5_schema()
    conn = engine.conn
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            changed_at TEXT NOT NULL,
            section TEXT NOT NULL,
            record_key TEXT,
            field_name TEXT,
            old_value TEXT,
            new_value TEXT,
            note TEXT
        );

        CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        """
    )
    conn.commit()
    engine._v6_schema_ready = True


def log_change(self: DatabaseCostingEngine, section: str, record_key: str = "", field_name: str = "", old_value: Any = None, new_value: Any = None, note: str = "") -> None:
    ensure_v6_schema(self)
    old_text = _as_text(old_value)
    new_text = _as_text(new_value)
    if old_text == new_text and not note:
        return
    self.conn.execute(
        """
        INSERT INTO audit_log(changed_at, section, record_key, field_name, old_value, new_value, note)
        VALUES(?,?,?,?,?,?,?)
        """,
        (datetime.now().isoformat(timespec="seconds"), section, record_key, field_name, old_text, new_text, note),
    )
    self.conn.commit()


def audit_log_rows(self: DatabaseCostingEngine, search: str = "", limit: int = 300) -> List[Dict[str, Any]]:
    ensure_v6_schema(self)
    params: List[Any] = []
    where = "WHERE 1=1"
    q = normalize(search)
    if q:
        where += " AND (section LIKE ? OR record_key LIKE ? OR field_name LIKE ? OR old_value LIKE ? OR new_value LIKE ? OR note LIKE ?)"
        like = f"%{q}%"
        params += [like] * 6
    params.append(int(limit))
    rows = self.conn.execute(
        f"""
        SELECT id, changed_at, section, record_key, field_name, old_value, new_value, note
        FROM audit_log
        {where}
        ORDER BY id DESC
        LIMIT ?
        """,
        tuple(params),
    ).fetchall()
    return [dict(r) for r in rows]


def clear_audit_log(self: DatabaseCostingEngine) -> None:
    ensure_v6_schema(self)
    self.conn.execute("DELETE FROM audit_log")
    self.conn.commit()


def validation_issues(self: DatabaseCostingEngine) -> List[Dict[str, Any]]:
    """Return admin warnings for missing/weak master data."""
    ensure_v6_schema(self)
    out: List[Dict[str, Any]] = []

    def add(severity: str, area: str, item: str, field: str, issue: str, suggestion: str = "") -> None:
        out.append({
            "Severity": severity,
            "Area": area,
            "Item / Record": item,
            "Field": field,
            "Issue": issue,
            "Suggestion": suggestion,
        })

    # MRP/final cost checks.
    for r in self.conn.execute("SELECT item, size_g, final_cost, mrp FROM new_cost_variations ORDER BY item, size_g").fetchall():
        label = f"{r['item']} / {int(r['size_g']) if r['size_g'] is not None else r['size_g']}g"
        if r["mrp"] is None or float(r["mrp"] or 0) <= 0:
            add("High", "MRP", label, "MRP", "MRP missing or zero", "Enter MRP in Master Data Center → MRP values.")
        if r["final_cost"] is None or float(r["final_cost"] or 0) <= 0:
            add("High", "Cost", label, "Final cost", "Final cost missing or zero", "Check product mappings and imported New Cost data.")

    # Missing packaging mapping where packing is required.
    reqs = self.conn.execute(
        """
        SELECT row_key AS item, row_key_norm, col_key_num AS size_g, value_num, value_text, value_kind
        FROM matrix_values
        WHERE table_name='packing_required' AND col_key_num IS NOT NULL
        ORDER BY row_key, col_key_num
        """
    ).fetchall()
    for r in reqs:
        req = deserialize(r)
        try:
            req_num = float(req or 0)
        except Exception:
            req_num = 0
        if req_num <= 0:
            continue
        for vendor_name, table in [("Maruthi Plastics", "maruthi_packaging"), ("Swiss Pac", "swiss_packaging")]:
            row = self.conn.execute(
                """
                SELECT value_text, value_num, value_kind FROM matrix_values
                WHERE table_name=? AND row_key_norm=? AND col_key_num=?
                LIMIT 1
                """,
                (table, r["row_key_norm"], r["size_g"]),
            ).fetchone()
            value = deserialize(row) if row else None
            if not normalize(value) or norm_key(value) in {"none", "na", "n/a"}:
                add("Medium", "Packaging Mapping", f"{r['item']} / {int(r['size_g'])}g / {vendor_name}", "Packaging material", "Packaging material not mapped", "Map product-size-vendor in Master Data Center → Packaging Mapping.")
            else:
                exists = self.conn.execute(
                    "SELECT active FROM packaging_materials WHERE material_norm=? LIMIT 1",
                    (norm_key(value),),
                ).fetchone()
                if not exists:
                    add("Medium", "Packaging Mapping", f"{r['item']} / {int(r['size_g'])}g / {vendor_name}", "Packaging material", f"'{value}' is mapped but not present in Packaging List", "Add it to Packaging List or remap the product.")
                elif int(exists["active"] or 0) != 1:
                    add("Medium", "Packaging Mapping", f"{r['item']} / {int(r['size_g'])}g / {vendor_name}", "Packaging material", f"'{value}' is inactive", "Activate the packaging material or choose another one.")

    # Raw transport/source checks.
    for r in self.conn.execute("SELECT * FROM raw_material_sources ORDER BY material_name, id").fetchall():
        d = dict(r)
        label = f"{d.get('material_name')} / {d.get('vendor_name') or 'No vendor'}"
        if int(d.get("active") or 0) == 1:
            if not normalize(d.get("transport_method")):
                add("High", "Transport", label, "Transport method", "Transport method missing", "Choose VRL or Direct.")
            if float(d.get("quantity_kg") or 0) <= 0:
                add("High", "Transport", label, "Quantity kg", "Quantity must be greater than zero", "Enter received/purchased quantity in kg.")
            if normalize(d.get("transport_method")) == "VRL" and float(d.get("vrl_state_to_mumbai_cost") or 0) == 0:
                add("Low", "Transport", label, "VRL state → Mumbai", "VRL selected but VRL leg is zero", "Enter VRL cost or confirm it is intentionally zero.")
            if normalize(d.get("transport_method")) == "Direct" and float(d.get("direct_transport_cost") or 0) == 0:
                add("Low", "Transport", label, "Direct transport", "Direct selected but direct transport is zero", "Enter direct transport or confirm it is intentionally zero.")

    # Recipe checks for in-house products.
    in_house = self.conn.execute(
        """
        SELECT DISTINCT item, item_norm, source FROM production_rows
        WHERE source='In House Production'
        ORDER BY item
        """
    ).fetchall()
    for r in in_house:
        exists = self.conn.execute("SELECT product_norm FROM recipe_headers WHERE product_norm=? AND active=1", (r["item_norm"],)).fetchone()
        if not exists:
            add("Medium", "BOM / Recipe", r["item"], "Recipe", "In-house product has no recipe in app", "Create recipe in BOM / Recipe Builder or keep using imported in-house rate.")

    return out


def create_product_v6(
    self: DatabaseCostingEngine,
    product_name: str,
    category: str,
    source_or_type: str,
    wholesale_ex_gst: Any = 0,
    retail_with_gst: Any = 0,
    gst_pct: Any = 0,
    sizes: Optional[List[Any]] = None,
    default_vendor: str = "Maruthi Plastics",
    default_shipping_pack: str = "Five Ply Box",
    packing_required_qty: Any = 1,
    default_packaging_material: str = "",
    sale_type: str = "Wholesale",
) -> None:
    """Create a product skeleton so it appears in calculator and mapping screens.

    This intentionally creates a safe skeleton, not a full polished product. Admin should then
    confirm packaging, MRP, transport and recipe details.
    """
    ensure_v6_schema(self)
    product = normalize(product_name)
    if not product:
        raise ValueError("Product name cannot be blank")
    sizes = sizes or [100]
    parsed_sizes = sorted({finite_number(s, "Product size", minimum=0.000001) for s in sizes})
    pkey = norm_key(product)
    gst = finite_number(gst_pct or 0, "GST percentage", minimum=0, maximum=100)
    wholesale_rate = finite_number(wholesale_ex_gst or 0, "Wholesale rate", minimum=0)
    retail_rate = finite_number(retail_with_gst or 0, "Retail rate", minimum=0)
    packing_qty = finite_number(packing_required_qty or 0, "Packing quantity", minimum=0)

    self.conn.execute(
        """
        INSERT OR REPLACE INTO item_catalog(item_norm,item_name,category,source_or_type,gst_pct,active,source_row_no)
        VALUES(?,?,?,?,?,?,COALESCE((SELECT source_row_no FROM item_catalog WHERE item_norm=?), NULL))
        """,
        (pkey, product, category, source_or_type, gst, 1, pkey),
    )

    # Add/update vlookup row so regular products have source and rates.
    existing = self.conn.execute("SELECT row_no FROM master_vlookup WHERE row_key_norm=? LIMIT 1", (pkey,)).fetchone()
    if existing:
        row_no = int(existing["row_no"])
    else:
        row_no = int(self.conn.execute("SELECT COALESCE(MAX(row_no),0)+1 AS n FROM master_vlookup").fetchone()["n"])
    for col, value in [(1, product), (2, source_or_type), (21, wholesale_rate), (22, retail_rate)]:
        text, num, kind = serialize(value)
        self.conn.execute(
            """
            INSERT OR REPLACE INTO master_vlookup(row_no,row_key,row_key_norm,col_index,value_text,value_num,value_kind)
            VALUES(?,?,?,?,?,?,?)
            """,
            (row_no, product, pkey, col, text, num, kind),
        )

    if normalize(source_or_type) == "In House Production":
        rate = wholesale_rate
        self.conn.execute("INSERT OR REPLACE INTO in_house_rates(row_no,item,item_norm,rate_per_g) VALUES(?,?,?,?)", (row_no, product, pkey, rate))

    # Production rows so calculator product_list sees it.
    max_prod = int(self.conn.execute("SELECT COALESCE(MAX(row_no),2) AS n FROM production_rows").fetchone()["n"])
    for i, size in enumerate(parsed_sizes, start=1):
        prod_row_no = max_prod + i
        self.conn.execute(
            """
            INSERT OR IGNORE INTO production_rows(row_no,item,item_norm,source,shipping_pack,size_g,sale_type,vendor,expected_total_cost)
            VALUES(?,?,?,?,?,?,?,?,NULL)
            """,
            (prod_row_no, product, pkey, source_or_type, default_shipping_pack, size, sale_type, default_vendor),
        )
        self.conn.execute(
            "INSERT OR IGNORE INTO new_cost_variations(item,item_norm,size_g,final_cost,mrp,profit) VALUES(?,?,?,NULL,NULL,NULL)",
            (product, pkey, size),
        )

    # Matrix skeleton cells for packing_required and both vendor mappings.
    def col_meta(table: str, size: float):
        row = self.conn.execute(
            """
            SELECT col_no,col_key,col_key_norm,col_key_num FROM matrix_values
            WHERE table_name=? AND col_key_num=? LIMIT 1
            """,
            (table, size),
        ).fetchone()
        return dict(row) if row else None

    def insert_matrix(table: str, size: float, value: Any):
        meta = col_meta(table, size)
        if not meta:
            return
        row_no = int(self.conn.execute("SELECT COALESCE(MAX(row_no),0)+1 AS n FROM matrix_values WHERE table_name=?", (table,)).fetchone()["n"])
        # Keep same row_no for all sizes of same product if already present in this table.
        existing_row = self.conn.execute("SELECT row_no FROM matrix_values WHERE table_name=? AND row_key_norm=? LIMIT 1", (table, pkey)).fetchone()
        if existing_row:
            row_no = int(existing_row["row_no"])
        text, num, kind = serialize(value)
        self.conn.execute(
            """
            INSERT OR REPLACE INTO matrix_values(table_name,row_no,col_no,row_key,row_key_norm,col_key,col_key_norm,col_key_num,value_text,value_num,value_kind)
            VALUES(?,?,?,?,?,?,?,?,?,?,?)
            """,
            (table, row_no, int(meta["col_no"]), product, pkey, meta["col_key"], meta["col_key_norm"], meta["col_key_num"], text, num, kind),
        )

    for size in parsed_sizes:
        insert_matrix("packing_required", size, packing_qty)
        insert_matrix("maruthi_packaging", size, default_packaging_material if default_vendor == "Maruthi Plastics" else "")
        insert_matrix("swiss_packaging", size, default_packaging_material if default_vendor == "Swiss Pac" else "")

    self.conn.commit()
    self.log_change("Product Creation", product, "create_product", "", f"category={category}; source={source_or_type}; sizes={parsed_sizes}", "Created product skeleton from app.")


# ------------------------------------------------------------------
# Monkey patches with audit logging
# ------------------------------------------------------------------

# Save old methods after v5 has patched the class.
_old_update_cell_value = getattr(DatabaseCostingEngine, "update_cell_value", None)
_old_update_master_value_by_row = getattr(DatabaseCostingEngine, "update_master_value_by_row", None)
_old_update_matrix_value = getattr(DatabaseCostingEngine, "update_matrix_value", None)
_old_update_item_catalog_row = getattr(DatabaseCostingEngine, "update_item_catalog_row", None)
_old_upsert_packaging_material = getattr(DatabaseCostingEngine, "upsert_packaging_material", None)
_old_delete_packaging_material = getattr(DatabaseCostingEngine, "delete_packaging_material", None)
_old_upsert_transport_source = getattr(DatabaseCostingEngine, "upsert_transport_source", None)
_old_save_recipe = getattr(DatabaseCostingEngine, "save_recipe", None)
_old_update_mrp_variation = getattr(DatabaseCostingEngine, "update_mrp_variation", None)


def update_cell_value_audit(self, sheet_name: str, cell_ref: str, value: Any) -> None:
    ensure_v6_schema(self)
    old = self.cell_value(sheet_name, cell_ref)
    _old_update_cell_value(self, sheet_name, cell_ref, value)
    self.log_change("Cell Setting", f"{sheet_name}!{cell_ref}", "value", old, value)


def update_master_value_by_row_audit(self, row_no: int, col_index: int, value: Any) -> None:
    ensure_v6_schema(self)
    old = self.master_value_by_row(row_no, col_index)
    _old_update_master_value_by_row(self, row_no, col_index, value)
    self.log_change("Master Rate", f"row {row_no}", f"col {col_index}", old, value)


def update_matrix_value_audit(self, table_name: str, row_no: int, col_no: int, value: Any) -> None:
    ensure_v6_schema(self)
    old_row = self.conn.execute(
        "SELECT value_text,value_num,value_kind,row_key,col_key FROM matrix_values WHERE table_name=? AND row_no=? AND col_no=?",
        (table_name, int(row_no), int(col_no)),
    ).fetchone()
    old = deserialize(old_row) if old_row else None
    rec = f"{table_name} / row {row_no} / col {col_no}"
    if old_row:
        rec = f"{table_name} / {old_row['row_key']} / {old_row['col_key']}"
    _old_update_matrix_value(self, table_name, row_no, col_no, value)
    self.log_change("Matrix Mapping", rec, "value", old, value)


def update_item_catalog_row_audit(self, item_norm: str, category: str, gst_pct: Any, active: bool) -> None:
    ensure_v6_schema(self)
    old = self.conn.execute("SELECT category,gst_pct,active,item_name FROM item_catalog WHERE item_norm=?", (item_norm,)).fetchone()
    _old_update_item_catalog_row(self, item_norm, category, gst_pct, active)
    if old:
        if _as_text(old["category"]) != _as_text(category):
            self.log_change("Item Catalog", old["item_name"], "category", old["category"], category)
        if _as_text(old["gst_pct"]) != _as_text(gst_pct):
            self.log_change("Item Catalog", old["item_name"], "gst_pct", old["gst_pct"], gst_pct)
        if int(old["active"] or 0) != int(bool(active)):
            self.log_change("Item Catalog", old["item_name"], "active", old["active"], int(bool(active)))


def upsert_packaging_material_audit(self, material_name: str, vendor: str, category: str, wholesale_ex_gst: Any, retail_with_gst: Any, gst_pct: Any, active: bool=True) -> None:
    ensure_v6_schema(self)
    key = norm_key(material_name)
    old = self.conn.execute("SELECT * FROM packaging_materials WHERE material_norm=?", (key,)).fetchone()
    old_d = dict(old) if old else {}
    _old_upsert_packaging_material(self, material_name, vendor, category, wholesale_ex_gst, retail_with_gst, gst_pct, active)
    new_d = {"vendor": vendor, "category": category, "wholesale_ex_gst": wholesale_ex_gst, "retail_with_gst": retail_with_gst, "gst_pct": gst_pct, "active": int(bool(active))}
    if not old:
        self.log_change("Packaging List", material_name, "create", "", json.dumps(new_d), "Added packaging material.")
    else:
        for f, newv in new_d.items():
            oldv = old_d.get(f)
            if _as_text(oldv) != _as_text(newv):
                self.log_change("Packaging List", material_name, f, oldv, newv)


def delete_packaging_material_audit(self, material_name: str) -> None:
    ensure_v6_schema(self)
    _old_delete_packaging_material(self, material_name)
    self.log_change("Packaging List", material_name, "active", "1", "0", "Deactivated packaging material.")


def upsert_transport_source_audit(self, row: Dict[str, Any]) -> None:
    ensure_v6_schema(self)
    old = None
    if row.get("id"):
        old = self.conn.execute("SELECT * FROM raw_material_sources WHERE id=?", (int(row["id"]),)).fetchone()
    _old_upsert_transport_source(self, row)
    label = normalize(row.get("material_name")) or f"id {row.get('id','new')}"
    if old:
        old_d = dict(old)
        for f in ["vendor_name","transport_method","base_material_cost_ex_gst","supplier_packing_cost","farmer_to_transporter_cost","vrl_state_to_mumbai_cost","mumbai_local_transport_cost","direct_transport_cost","quantity_kg","gst_pct","active"]:
            if _as_text(old_d.get(f)) != _as_text(row.get(f)):
                self.log_change("Transport + GST", label, f, old_d.get(f), row.get(f))
    else:
        self.log_change("Transport + GST", label, "create", "", json.dumps(row, default=str), "Added raw material source row.")


def save_recipe_audit(
    self,
    product: str,
    ingredients: List[Dict[str, Any]],
    notes: str='',
    overhead_pct: Any=None,
    use_for_costing: Any=None,
) -> None:
    ensure_v6_schema(self)
    before = self.recipe_ingredients(product) if hasattr(self, "recipe_ingredients") else []
    _old_save_recipe(self, product, ingredients, notes, overhead_pct, use_for_costing)
    self.log_change("Recipe", product, "ingredients", json.dumps(before, default=str), json.dumps(ingredients, default=str), "Recipe saved.")


def update_mrp_variation_audit(self, item_norm: str, size_g: Any, mrp: Any) -> None:
    ensure_v6_schema(self)
    old = self.conn.execute("SELECT item,mrp FROM new_cost_variations WHERE item_norm=? AND size_g=?", (item_norm, float(as_number(size_g)))).fetchone()
    old_mrp = old["mrp"] if old else None
    _old_update_mrp_variation(self, item_norm, size_g, mrp)
    self.log_change("MRP", f"{old['item'] if old else item_norm} / {size_g}g", "mrp", old_mrp, mrp)


# Attach methods
for name, fn in {
    "ensure_v6_schema": ensure_v6_schema,
    "log_change": log_change,
    "audit_log_rows": audit_log_rows,
    "clear_audit_log": clear_audit_log,
    "validation_issues": validation_issues,
    "create_product_v6": create_product_v6,
}.items():
    setattr(DatabaseCostingEngine, name, fn)

# Replace existing methods with audited versions where present.
if _old_update_cell_value:
    DatabaseCostingEngine.update_cell_value = update_cell_value_audit
if _old_update_master_value_by_row:
    DatabaseCostingEngine.update_master_value_by_row = update_master_value_by_row_audit
if _old_update_matrix_value:
    DatabaseCostingEngine.update_matrix_value = update_matrix_value_audit
if _old_update_item_catalog_row:
    DatabaseCostingEngine.update_item_catalog_row = update_item_catalog_row_audit
if _old_upsert_packaging_material:
    DatabaseCostingEngine.upsert_packaging_material = upsert_packaging_material_audit
if _old_delete_packaging_material:
    DatabaseCostingEngine.delete_packaging_material = delete_packaging_material_audit
if _old_upsert_transport_source:
    DatabaseCostingEngine.upsert_transport_source = upsert_transport_source_audit
if _old_save_recipe:
    DatabaseCostingEngine.save_recipe = save_recipe_audit
if _old_update_mrp_variation:
    DatabaseCostingEngine.update_mrp_variation = update_mrp_variation_audit

# Extend DB check version label.
_old_database_check_v6_base = DatabaseCostingEngine.database_check

def _database_check_v6(self) -> Dict[str, Any]:
    ensure_v6_schema(self)
    base = _old_database_check_v6_base(self)
    for table in ["audit_log", "app_settings"]:
        try:
            base["counts"][table] = self.conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"]
        except Exception:
            base["counts"][table] = None
    base["meta"]["app_version"] = "6"
    return base

DatabaseCostingEngine.database_check = _database_check_v6
