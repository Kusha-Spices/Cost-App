from __future__ import annotations

from typing import Any, Dict, List, Optional
import math
import sqlite3

from database_engine import DatabaseCostingEngine, normalize, norm_key, as_number, finite_number, serialize, deserialize

RAW_CATEGORY_WORDS = {
    'cardamom','pepper','cinnamon','clove','coriander','cumin','mustard','mace','nutmeg','bay leaf','chilli','chili','turmeric','asafoetida','saffron','star anise','sesame','fenugreek','ajwain','carrom','fennel','amchur','mango powder','kasuri','garlic','ginger','kalongi','anardana','pippali','stone flower','long pepper','caraway','salt'
}
PACKAGING_WORDS = {'pouch','box','kraft','foil','zipper','label','sticker','bottle','jar','ply','bubble','tape','carton'}
FINISHED_WORDS = {'masala','powder','pickle','blend','podi','metkut','chutney','immunity','haldi doodh','guco'}


def guess_category(name: Any, source_or_type: Any = None) -> str:
    n = norm_key(name)
    s = norm_key(source_or_type)
    if any(w in n for w in PACKAGING_WORDS) or any(w in s for w in ['packaging','packing']):
        if any(w in n for w in ['box','ply','bubble','carton','tape']):
            return 'Shipping Packing Material'
        return 'Packaging Material'
    if any(w in n for w in FINISHED_WORDS) or 'in house production' in s:
        if 'pickle' in n:
            return 'Pickle / Finished Product'
        if 'blend' in n or 'masala' in n or 'podi' in n or 'powder' in n:
            return 'Masala / Blend / Finished Product'
        return 'Finished Product'
    if any(w in n for w in RAW_CATEGORY_WORDS):
        return 'Raw Material'
    return 'Other / Review'


def _exec(conn: sqlite3.Connection, sql: str, params: tuple = ()):
    return conn.execute(sql, params)


def ensure_v5_schema(engine: DatabaseCostingEngine) -> None:
    """Create and seed the structured V5 tables. Safe to call repeatedly."""
    if getattr(engine, "_v5_schema_ready", False):
        return
    conn = engine.conn
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS item_catalog (
            item_norm TEXT PRIMARY KEY,
            item_name TEXT NOT NULL,
            category TEXT,
            source_or_type TEXT,
            gst_pct REAL DEFAULT 0,
            active INTEGER DEFAULT 1,
            source_row_no INTEGER
        );

        CREATE TABLE IF NOT EXISTS packaging_materials (
            material_norm TEXT PRIMARY KEY,
            material_name TEXT NOT NULL,
            vendor TEXT DEFAULT '',
            category TEXT DEFAULT 'Packaging Material',
            wholesale_ex_gst REAL,
            retail_with_gst REAL,
            gst_pct REAL DEFAULT 0,
            active INTEGER DEFAULT 1,
            source_row_no INTEGER
        );

        CREATE TABLE IF NOT EXISTS raw_material_sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            material_norm TEXT NOT NULL,
            material_name TEXT NOT NULL,
            vendor_name TEXT,
            transport_method TEXT DEFAULT 'VRL',
            base_material_cost_ex_gst REAL DEFAULT 0,
            supplier_packing_cost REAL DEFAULT 0,
            farmer_to_transporter_cost REAL DEFAULT 0,
            vrl_state_to_mumbai_cost REAL DEFAULT 0,
            mumbai_local_transport_cost REAL DEFAULT 0,
            direct_transport_cost REAL DEFAULT 0,
            quantity_kg REAL DEFAULT 1,
            gst_pct REAL DEFAULT 0,
            active INTEGER DEFAULT 0,
            notes TEXT
        );

        CREATE TABLE IF NOT EXISTS recipe_headers (
            product_norm TEXT PRIMARY KEY,
            product_name TEXT NOT NULL,
            basis_g REAL DEFAULT 1000,
            active INTEGER DEFAULT 1,
            notes TEXT,
            overhead_pct REAL DEFAULT 0,
            use_for_costing INTEGER DEFAULT 0,
            source_recipe_name TEXT
        );

        CREATE TABLE IF NOT EXISTS recipe_ingredients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_norm TEXT NOT NULL,
            ingredient_norm TEXT NOT NULL,
            ingredient_name TEXT NOT NULL,
            qty_g_per_kg REAL NOT NULL,
            FOREIGN KEY(product_norm) REFERENCES recipe_headers(product_norm) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS shipping_zone_weights (
            zone_key TEXT PRIMARY KEY,
            zone_name TEXT NOT NULL,
            cost_1kg REAL NOT NULL,
            weight_pct REAL NOT NULL
        );
        """
    )

    for stmt in [
        "ALTER TABLE recipe_headers ADD COLUMN overhead_pct REAL DEFAULT 0",
        "ALTER TABLE recipe_headers ADD COLUMN use_for_costing INTEGER DEFAULT 0",
        "ALTER TABLE recipe_headers ADD COLUMN source_recipe_name TEXT",
    ]:
        try:
            cur.execute(stmt)
        except sqlite3.OperationalError:
            pass

    # Seed item catalog from master_vlookup.
    rows = conn.execute(
        """
        SELECT k.row_no, k.row_key, s.value_text AS source_text, s.value_num AS source_num, s.value_kind AS source_kind,
               w.value_num AS wholesale, r.value_num AS retail
        FROM master_vlookup k
        LEFT JOIN master_vlookup s ON s.row_no=k.row_no AND s.col_index=2
        LEFT JOIN master_vlookup w ON w.row_no=k.row_no AND w.col_index=21
        LEFT JOIN master_vlookup r ON r.row_no=k.row_no AND r.col_index=22
        WHERE k.col_index=1 AND k.row_key IS NOT NULL AND TRIM(k.row_key) <> ''
        ORDER BY k.row_no
        """
    ).fetchall()
    for row in rows:
        item_name = normalize(row['row_key'])
        if not item_name:
            continue
        source = None
        if row['source_kind']:
            source = deserialize({'value_text': row['source_text'], 'value_num': row['source_num'], 'value_kind': row['source_kind']})
        cat = guess_category(item_name, source)
        # default GST: packaging 18, raw/finished 0 until admin sets item-level GST.
        default_gst = 18.0 if 'Packaging' in cat else 0.0
        conn.execute(
            """
            INSERT OR IGNORE INTO item_catalog(item_norm,item_name,category,source_or_type,gst_pct,active,source_row_no)
            VALUES(?,?,?,?,?,?,?)
            """,
            (norm_key(item_name), item_name, cat, None if source is None else str(source), default_gst, 1, row['row_no'])
        )

    # Seed packaging master from mapped values and shipping packs.
    names = set()
    for row in conn.execute(
        """
        SELECT value_text AS name FROM matrix_values
        WHERE table_name IN ('maruthi_packaging', 'swiss_packaging') AND value_text IS NOT NULL AND TRIM(value_text)<>''
        UNION
        SELECT shipping_pack AS name FROM production_rows WHERE shipping_pack IS NOT NULL AND TRIM(shipping_pack)<>''
        """
    ):
        nm = normalize(row['name'])
        if nm and norm_key(nm) not in {'none','na','n/a'}:
            names.add(nm)
    for name in names:
        row = conn.execute("SELECT row_no FROM master_vlookup WHERE row_key_norm=? ORDER BY row_no LIMIT 1", (norm_key(name),)).fetchone()
        row_no = int(row['row_no']) if row else None
        wholesale = engine.master_value_by_row(row_no, 21) if row_no else None
        retail = engine.master_value_by_row(row_no, 22) if row_no else None
        lname = norm_key(name)
        category = 'Shipping Packing Material' if any(x in lname for x in ['box','ply','bubble','carton','tape']) else 'Packaging Material'
        vendor = 'Maruthi Plastics' if row_no and row_no < 255 else ('Swiss Pac' if row_no and row_no >= 255 else '')
        conn.execute(
            """
            INSERT OR IGNORE INTO packaging_materials(material_norm, material_name, vendor, category, wholesale_ex_gst, retail_with_gst, gst_pct, active, source_row_no)
            VALUES(?,?,?,?,?,?,?,?,?)
            """,
            (norm_key(name), name, vendor, category, float(wholesale) if isinstance(wholesale,(int,float)) else None, float(retail) if isinstance(retail,(int,float)) else None, 18.0, 1, row_no)
        )


    # Seed raw material source/transport records from item catalog so the Transport + GST tab is not blank.
    # We seed one default editable row per raw material using the current Master Data landed rate as
    # the base material cost for 1 kg. Admin can then change VRL/Direct transport details.
    raw_rows = conn.execute(
        """
        SELECT item_norm, item_name, source_or_type, gst_pct, source_row_no
        FROM item_catalog
        WHERE active=1 AND category IN ('Raw Material', 'Masala / Blend / Finished Product', 'Finished Product', 'Pickle / Finished Product')
        ORDER BY item_name
        """
    ).fetchall()
    for rr in raw_rows:
        # Avoid creating duplicates. A material may have multiple sources later, but the importer seeds only one default row.
        exists = conn.execute(
            "SELECT id FROM raw_material_sources WHERE material_norm=? LIMIT 1",
            (rr['item_norm'],)
        ).fetchone()
        if exists:
            continue
        row_no = rr['source_row_no']
        wh_rate = engine.master_value_by_row(row_no, 21) if row_no else None  # rate per gram in current master data
        try:
            base_cost_1kg = float(wh_rate or 0) * 1000
        except Exception:
            base_cost_1kg = 0.0
        vendor_name = rr['source_or_type'] or ''
        # Only seed meaningful source rows.
        conn.execute(
            """
            INSERT INTO raw_material_sources(
                material_norm, material_name, vendor_name, transport_method,
                base_material_cost_ex_gst, supplier_packing_cost, farmer_to_transporter_cost,
                vrl_state_to_mumbai_cost, mumbai_local_transport_cost, direct_transport_cost,
                quantity_kg, gst_pct, active, notes
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                rr['item_norm'], rr['item_name'], vendor_name, 'VRL',
                base_cost_1kg, 0.0, 0.0, 0.0, 0.0, 0.0,
                1.0, float(rr['gst_pct'] or 0), 0, 'Auto-seeded from Master Data. Turn on Use for costing after entering transport details.'
            )
        )

    # Seed current shipping formula assumptions (editable later).
    defaults = [
        ('within_city', 'Within city', 54.0, 80.0),
        ('within_state', 'Within state', 55.0, 10.0),
        ('metro_to_metro', 'Metro to metro', 73.0, 5.0),
        ('rest_of_india', 'Rest of India', 84.0, 5.0),
    ]
    for zone_key, zone_name, cost, pct in defaults:
        conn.execute(
            "INSERT OR IGNORE INTO shipping_zone_weights(zone_key,zone_name,cost_1kg,weight_pct) VALUES(?,?,?,?)",
            (zone_key, zone_name, cost, pct)
        )
    conn.commit()
    engine._v5_schema_ready = True


# -----------------------
# V5 helper methods
# -----------------------

def item_categories(self) -> List[str]:
    ensure_v5_schema(self)
    rows = self.conn.execute("SELECT DISTINCT category FROM item_catalog WHERE category IS NOT NULL ORDER BY category").fetchall()
    return [r['category'] for r in rows]


def list_master_rate_rows_v5(self, search: str = '', category: str = 'All', limit: int = 500) -> List[Dict[str, Any]]:
    ensure_v5_schema(self)
    params: List[Any] = []
    where = "WHERE 1=1"
    if normalize(search):
        where += " AND item_norm LIKE ?"
        params.append(f"%{norm_key(search)}%")
    if category and category != 'All':
        where += " AND category=?"
        params.append(category)
    params.append(int(limit))
    rows = self.conn.execute(
        f"""
        SELECT item_norm,item_name,category,source_or_type,gst_pct,active,source_row_no
        FROM item_catalog
        {where}
        ORDER BY item_name
        LIMIT ?
        """,
        tuple(params),
    ).fetchall()
    out=[]
    for r in rows:
        row_no = r['source_row_no']
        wholesale = self.master_value_by_row(row_no,21) if row_no else None
        retail = self.master_value_by_row(row_no,22) if row_no else None
        out.append({
            'item_norm': r['item_norm'],
            'row_no': row_no,
            'name': r['item_name'],
            'category': r['category'],
            'source_or_type': r['source_or_type'],
            'gst_pct': r['gst_pct'],
            'wholesale_ex_gst': wholesale,
            'retail_with_gst': retail,
            'active': bool(r['active']),
        })
    return out


def update_item_catalog_row(self, item_norm: str, category: str, gst_pct: Any, active: Any=True) -> None:
    ensure_v5_schema(self)
    gst = finite_number(gst_pct or 0, "GST percentage", minimum=0, maximum=100)
    self.conn.execute("UPDATE item_catalog SET category=?, gst_pct=?, active=? WHERE item_norm=?", (category, gst, int(bool(active)), item_norm))
    self.conn.commit()


def item_gst_pct(self, item: str) -> float:
    ensure_v5_schema(self)
    row = self.conn.execute("SELECT gst_pct FROM item_catalog WHERE item_norm=?", (norm_key(item),)).fetchone()
    return float(row['gst_pct'] or 0) if row else 0.0


def packaging_material_options(self, vendor: Optional[str]=None, include_inactive: bool=False, category: Optional[str]=None) -> List[str]:
    ensure_v5_schema(self)
    where = "WHERE 1=1"
    params=[]
    if vendor:
        where += " AND (vendor=? OR vendor='' OR vendor IS NULL)"
        params.append(vendor)
    if not include_inactive:
        where += " AND active=1"
    if category:
        where += " AND category=?"
        params.append(category)
    rows = self.conn.execute(f"SELECT material_name FROM packaging_materials {where} ORDER BY material_name", tuple(params)).fetchall()
    return [r['material_name'] for r in rows]


def list_packaging_materials(self, search: str='', vendor: str='All', include_inactive: bool=True, limit: int=500) -> List[Dict[str, Any]]:
    ensure_v5_schema(self)
    where="WHERE 1=1"
    params=[]
    if normalize(search):
        where += " AND material_norm LIKE ?"
        params.append(f"%{norm_key(search)}%")
    if vendor and vendor != 'All':
        where += " AND vendor=?"
        params.append(vendor)
    if not include_inactive:
        where += " AND active=1"
    params.append(int(limit))
    rows=self.conn.execute(f"SELECT * FROM packaging_materials {where} ORDER BY vendor, material_name LIMIT ?", tuple(params)).fetchall()
    return [dict(r) for r in rows]


def upsert_master_rate(self, name: str, source_or_type: str, wholesale: Any, retail: Any) -> int:
    key=norm_key(name)
    row=self.conn.execute("SELECT row_no FROM master_vlookup WHERE row_key_norm=? ORDER BY row_no LIMIT 1", (key,)).fetchone()
    if row:
        row_no=int(row['row_no'])
    else:
        maxrow=self.conn.execute("SELECT COALESCE(MAX(row_no),0)+1 AS n FROM master_vlookup").fetchone()['n']
        row_no=int(maxrow)
        for col_index, value in [(1,name),(2,source_or_type)]:
            text,num,kind=serialize(value)
            self.conn.execute("INSERT OR REPLACE INTO master_vlookup(row_no,row_key,row_key_norm,col_index,value_text,value_num,value_kind) VALUES(?,?,?,?,?,?,?)", (row_no,name,key,col_index,text,num,kind))
    for col_index, value in [(1,name),(2,source_or_type),(21,wholesale),(22,retail)]:
        text,num,kind=serialize(value)
        self.conn.execute("INSERT OR REPLACE INTO master_vlookup(row_no,row_key,row_key_norm,col_index,value_text,value_num,value_kind) VALUES(?,?,?,?,?,?,?)", (row_no,name,key,col_index,text,num,kind))
    self.conn.commit()
    return row_no


def upsert_packaging_material(self, material_name: str, vendor: str, category: str, wholesale_ex_gst: Any, retail_with_gst: Any, gst_pct: Any, active: bool=True) -> None:
    ensure_v5_schema(self)
    material_name=normalize(material_name)
    if not material_name:
        raise ValueError('Packaging material name cannot be blank')
    wholesale = finite_number(wholesale_ex_gst or 0, "Wholesale packaging rate", minimum=0)
    retail = finite_number(retail_with_gst or 0, "Retail packaging rate", minimum=0)
    gst = finite_number(gst_pct or 0, "GST percentage", minimum=0, maximum=100)
    row_no=upsert_master_rate(self, material_name, category, wholesale, retail)
    self.conn.execute(
        """
        INSERT OR REPLACE INTO packaging_materials(material_norm,material_name,vendor,category,wholesale_ex_gst,retail_with_gst,gst_pct,active,source_row_no)
        VALUES(?,?,?,?,?,?,?,?,?)
        """,
        (norm_key(material_name), material_name, vendor or '', category or 'Packaging Material', wholesale, retail, gst, int(bool(active)), row_no)
    )
    self.conn.commit()


def delete_packaging_material(self, material_name: str) -> None:
    ensure_v5_schema(self)
    self.conn.execute("UPDATE packaging_materials SET active=0 WHERE material_norm=?", (norm_key(material_name),))
    self.conn.commit()


def update_shipping_zones(self, rows: List[Dict[str, Any]]) -> None:
    ensure_v5_schema(self)
    cleaned = []
    for r in rows:
        cleaned.append(
            (
                r["zone_name"],
                finite_number(r.get("cost_1kg") or 0, "Shipping cost", minimum=0),
                finite_number(r.get("weight_pct") or 0, "Shipping-zone weight", minimum=0),
                r["zone_key"],
            )
        )
    if sum(row[2] for row in cleaned) <= 0:
        raise ValueError("Shipping-zone weights must total more than zero")
    for row in cleaned:
        self.conn.execute(
            "UPDATE shipping_zone_weights SET zone_name=?, cost_1kg=?, weight_pct=? WHERE zone_key=?",
            row,
        )
    self.conn.commit()


def shipping_zone_rows(self) -> List[Dict[str, Any]]:
    ensure_v5_schema(self)
    rows=self.conn.execute("SELECT zone_key, zone_name, cost_1kg, weight_pct FROM shipping_zone_weights ORDER BY rowid").fetchall()
    return [dict(r) for r in rows]


def weighted_shipping_1kg(self) -> float:
    ensure_v5_schema(self)
    rows=shipping_zone_rows(self)
    total_pct=sum(float(r['weight_pct'] or 0) for r in rows) or 100.0
    return sum(float(r['cost_1kg'] or 0)*float(r['weight_pct'] or 0)/total_pct for r in rows)


def apply_weighted_shipping_to_cells(self) -> Dict[str,float]:
    base=weighted_shipping_1kg(self)
    values={'AB32':base,'AB33':base/2,'AB34':base/3,'AB35':base/4,'AB36':base/6,'AB37':base/8,'AB38':base/8}
    for cell, val in values.items():
        self.update_cell_value('Master Data', cell, val)
    return values


def transport_source_rows(self, search: str='', limit: int=500) -> List[Dict[str, Any]]:
    ensure_v5_schema(self)
    where='WHERE 1=1'
    params=[]
    if normalize(search):
        where += ' AND (material_norm LIKE ? OR LOWER(material_name) LIKE ? OR LOWER(vendor_name) LIKE ?)'
        q = f"%{norm_key(search)}%"
        params.extend([q, q, q])
    params.append(int(limit))
    rows=self.conn.execute(f"SELECT * FROM raw_material_sources {where} ORDER BY material_name, active DESC LIMIT ?", tuple(params)).fetchall()
    out=[]
    for r in rows:
        d=dict(r)
        qty=float(d.get('quantity_kg') or 0)
        transport = (float(d.get('supplier_packing_cost') or 0) + float(d.get('farmer_to_transporter_cost') or 0) + float(d.get('mumbai_local_transport_cost') or 0))
        if (d.get('transport_method') or 'VRL') == 'VRL':
            transport += float(d.get('vrl_state_to_mumbai_cost') or 0)
        else:
            transport += float(d.get('direct_transport_cost') or 0)
        total = float(d.get('base_material_cost_ex_gst') or 0) + transport
        d['transport_total'] = transport
        d['landed_cost_per_g'] = total/(qty*1000) if qty>0 else None
        out.append(d)
    return out


def upsert_transport_source(self, row: Dict[str, Any]) -> None:
    ensure_v5_schema(self)
    material_name=normalize(row.get('material_name'))
    if not material_name:
        raise ValueError('Material name cannot be blank')
    active = int(bool(row.get("active")))
    quantity = finite_number(row.get("quantity_kg") if row.get("quantity_kg") not in (None, "") else 0, "Quantity kg", minimum=0)
    if active and quantity <= 0:
        raise ValueError("Quantity kg must be greater than zero for an active source")
    gst = finite_number(row.get("gst_pct") or 0, "GST percentage", minimum=0, maximum=100)
    data=(
        norm_key(material_name), material_name, row.get('vendor_name') or '', row.get('transport_method') or 'VRL',
        finite_number(row.get('base_material_cost_ex_gst') or 0, "Material cost", minimum=0),
        finite_number(row.get('supplier_packing_cost') or 0, "Supplier packing cost", minimum=0),
        finite_number(row.get('farmer_to_transporter_cost') or 0, "Farmer-to-transporter cost", minimum=0),
        finite_number(row.get('vrl_state_to_mumbai_cost') or 0, "VRL cost", minimum=0),
        finite_number(row.get('mumbai_local_transport_cost') or 0, "Mumbai local transport", minimum=0),
        finite_number(row.get('direct_transport_cost') or 0, "Direct transport", minimum=0),
        quantity, gst, active, row.get('notes') or ''
    )
    row_id = row.get("id")
    has_id = row_id not in (None, "")
    if has_id:
        try:
            has_id = not math.isnan(float(row_id))
        except (TypeError, ValueError):
            has_id = True
    if has_id:
        self.conn.execute(
            """
            UPDATE raw_material_sources SET material_norm=?, material_name=?, vendor_name=?, transport_method=?, base_material_cost_ex_gst=?,
            supplier_packing_cost=?, farmer_to_transporter_cost=?, vrl_state_to_mumbai_cost=?, mumbai_local_transport_cost=?, direct_transport_cost=?,
            quantity_kg=?, gst_pct=?, active=?, notes=? WHERE id=?
            """,
            data + (int(row_id),)
        )
    else:
        self.conn.execute(
            """
            INSERT INTO raw_material_sources(material_norm,material_name,vendor_name,transport_method,base_material_cost_ex_gst,supplier_packing_cost,
            farmer_to_transporter_cost,vrl_state_to_mumbai_cost,mumbai_local_transport_cost,direct_transport_cost,quantity_kg,gst_pct,active,notes)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, data
        )
    self.conn.commit()


def raw_source_rate_per_g(self, item: str, sale_type: str='Wholesale') -> Optional[float]:
    ensure_v5_schema(self)
    row=self.conn.execute("SELECT * FROM raw_material_sources WHERE material_norm=? AND active=1 ORDER BY id DESC LIMIT 1", (norm_key(item),)).fetchone()
    if not row:
        return None
    d=dict(row)
    qty=float(d.get('quantity_kg') or 0)
    if qty <= 0:
        return None
    transport = float(d.get('supplier_packing_cost') or 0) + float(d.get('farmer_to_transporter_cost') or 0) + float(d.get('mumbai_local_transport_cost') or 0)
    if (d.get('transport_method') or 'VRL') == 'VRL':
        transport += float(d.get('vrl_state_to_mumbai_cost') or 0)
    else:
        transport += float(d.get('direct_transport_cost') or 0)
    total = float(d.get('base_material_cost_ex_gst') or 0) + transport
    # GST shown separately by design; not absorbed into the wholesale rate.
    return total/(qty*1000)


def recipe_products(self) -> List[str]:
    ensure_v5_schema(self)
    rows=self.conn.execute("SELECT product_name FROM recipe_headers ORDER BY product_name").fetchall()
    return [r['product_name'] for r in rows]


def recipe_header(self, product: str) -> Optional[Dict[str, Any]]:
    ensure_v5_schema(self)
    row=self.conn.execute(
        """
        SELECT product_name,basis_g,active,notes,overhead_pct,use_for_costing,source_recipe_name
        FROM recipe_headers WHERE product_norm=?
        """,
        (norm_key(product),),
    ).fetchone()
    return dict(row) if row else None


def recipe_ingredients(self, product: str) -> List[Dict[str, Any]]:
    ensure_v5_schema(self)
    rows=self.conn.execute("SELECT id, ingredient_name, qty_g_per_kg FROM recipe_ingredients WHERE product_norm=? ORDER BY id", (norm_key(product),)).fetchall()
    return [dict(r) for r in rows]


def save_recipe(
    self,
    product: str,
    ingredients: List[Dict[str, Any]],
    notes: str='',
    overhead_pct: Any=None,
    use_for_costing: Any=None,
) -> None:
    ensure_v5_schema(self)
    product=normalize(product)
    if not product:
        raise ValueError('Product name cannot be blank')
    pkey=norm_key(product)
    cleaned = []
    for ing in ingredients:
        name=normalize(ing.get('ingredient_name'))
        qty=finite_number(ing.get('qty_g_per_kg') or 0, "Recipe ingredient quantity", minimum=0)
        if name and qty>0:
            cleaned.append((pkey,norm_key(name),name,qty))
    total_qty = sum(row[3] for row in cleaned)
    if cleaned and abs(total_qty - 1000) > 0.1:
        raise ValueError(f"Recipe quantities must total 1,000g; current total is {total_qty:g}g")
    existing = recipe_header(self, product) or {}
    if overhead_pct is None:
        overhead = float(existing.get('overhead_pct') or 0)
    else:
        overhead = finite_number(overhead_pct, "Recipe processing / energy and miscellaneous percentage", minimum=0, maximum=100)
    if use_for_costing is None:
        costing_flag = int(bool(existing.get('use_for_costing', 0)))
    else:
        costing_flag = int(bool(use_for_costing))
    source_recipe_name = existing.get('source_recipe_name')
    self.conn.execute(
        """
        INSERT OR REPLACE INTO recipe_headers
        (product_norm,product_name,basis_g,active,notes,overhead_pct,use_for_costing,source_recipe_name)
        VALUES(?,?,?,?,?,?,?,?)
        """,
        (pkey,product,1000,1,notes,overhead,costing_flag,source_recipe_name),
    )
    self.conn.execute("DELETE FROM recipe_ingredients WHERE product_norm=?", (pkey,))
    for values in cleaned:
        self.conn.execute("INSERT INTO recipe_ingredients(product_norm,ingredient_norm,ingredient_name,qty_g_per_kg) VALUES(?,?,?,?)", values)
    self.conn.commit()


def recipe_cost_per_kg(self, product: str, sale_type: str='Wholesale') -> Optional[Dict[str, Any]]:
    ensure_v5_schema(self)
    rows=recipe_ingredients(self, product)
    if not rows:
        return None
    total=0.0
    details=[]
    for r in rows:
        ing=r['ingredient_name']
        qty=float(r['qty_g_per_kg'] or 0)
        rate=raw_source_rate_per_g(self, ing, sale_type)
        if rate is None:
            col=21 if norm_key(sale_type)=='wholesale' else 22
            try:
                rate=float(self.vlookup_master(ing, col) or 0)
            except Exception:
                rate=0.0
        cost=rate*qty
        total += cost
        details.append({'Ingredient': ing, 'Qty g/kg': qty, 'Rate / g': rate, 'Cost': cost})
    header = recipe_header(self, product) or {}
    overhead_pct = float(header.get('overhead_pct') or 0)
    overhead_cost = total * overhead_pct / 100
    final_total = total + overhead_cost
    return {
        'ingredient_cost_per_kg': total,
        'overhead_pct': overhead_pct,
        'overhead_cost': overhead_cost,
        'cost_per_kg': final_total,
        'rate_per_g': final_total/1000,
        'details': details,
    }


# Monkey patch landed rate to use recipe if available, then active source cost if available.
_old_landed = DatabaseCostingEngine._landed_rate_per_g

def _landed_rate_per_g_v5(self, item: str, source: str, sale_type: str) -> float:
    try:
        ensure_v5_schema(self)
        if normalize(source) == 'In House Production':
            header = recipe_header(self, item)
            if header and int(header.get('use_for_costing') or 0) == 1:
                recipe = recipe_cost_per_kg(self, item, sale_type)
                if recipe is not None:
                    return float(recipe['rate_per_g'])
        src_rate = raw_source_rate_per_g(self, item, sale_type)
        if src_rate is not None and normalize(source) != 'In House Production':
            return float(src_rate)
    except Exception:
        pass
    return _old_landed(self, item, source, sale_type)


# Attach methods to DatabaseCostingEngine
for name, fn in {
    'ensure_v5_schema': ensure_v5_schema,
    'item_categories': item_categories,
    'list_master_rate_rows_v5': list_master_rate_rows_v5,
    'update_item_catalog_row': update_item_catalog_row,
    'item_gst_pct': item_gst_pct,
    'packaging_material_options': packaging_material_options,
    'list_packaging_materials': list_packaging_materials,
    'upsert_master_rate': upsert_master_rate,
    'upsert_packaging_material': upsert_packaging_material,
    'delete_packaging_material': delete_packaging_material,
    'shipping_zone_rows': shipping_zone_rows,
    'update_shipping_zones': update_shipping_zones,
    'weighted_shipping_1kg': weighted_shipping_1kg,
    'apply_weighted_shipping_to_cells': apply_weighted_shipping_to_cells,
    'transport_source_rows': transport_source_rows,
    'upsert_transport_source': upsert_transport_source,
    'raw_source_rate_per_g': raw_source_rate_per_g,
    'recipe_products': recipe_products,
    'recipe_header': recipe_header,
    'recipe_ingredients': recipe_ingredients,
    'save_recipe': save_recipe,
    'recipe_cost_per_kg': recipe_cost_per_kg,
}.items():
    setattr(DatabaseCostingEngine, name, fn)

DatabaseCostingEngine._landed_rate_per_g = _landed_rate_per_g_v5

# Extend database check with Version 5 structured tables.
_old_database_check = DatabaseCostingEngine.database_check

def _database_check_v5(self) -> Dict[str, Any]:
    ensure_v5_schema(self)
    base = _old_database_check(self)
    for table in [
        'item_catalog', 'packaging_materials', 'raw_material_sources',
        'recipe_headers', 'recipe_ingredients', 'shipping_zone_weights'
    ]:
        try:
            base['counts'][table] = self.conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()['n']
        except Exception:
            base['counts'][table] = None
    base['meta']['app_version'] = '5'
    return base

DatabaseCostingEngine.database_check = _database_check_v5
