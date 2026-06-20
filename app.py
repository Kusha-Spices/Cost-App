from __future__ import annotations

import os
from pathlib import Path
import tempfile
import shutil
from datetime import datetime

import pandas as pd
import streamlit as st

from database_engine import CostingDatabase, DatabaseCostingEngine, normalize, norm_key
import v5_extensions  # installs Version 5 structured-data helpers
import v6_extensions  # installs Version 6 audit, validation and product setup helpers
import v7_extensions  # installs Version 7 Excel export + launcher notes
import v9_extensions  # installs Version 9 MRP/product management + reconciliation (Excel-free)


APP_DIR = Path(__file__).parent
# When packaged as a Mac/Windows app the code lives in a read-only bundle, so the
# database is kept in a user-writable location supplied via KUSHA_DATA_DIR.
DATA_DIR = Path(os.environ.get("KUSHA_DATA_DIR") or (APP_DIR / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DEFAULT_WORKBOOK = DATA_DIR / "Cost Sheet 2026 new(3).xlsx"
DEFAULT_DB = DATA_DIR / "kusha_costing_v8.3.sqlite"

st.set_page_config(page_title="Kusha Costing App", page_icon="🌶️", layout="wide")

st.title("Kusha Spices Costing App")
st.caption("Version 9.0 — fully app-driven costing & pricing; the SQLite database is the source of truth (Excel optional)")


def ensure_database(db_path: Path, workbook_path: Path) -> None:
    if not db_path.exists():
        db = CostingDatabase(db_path)
        db.import_workbook(workbook_path)
        db.close()


@st.cache_resource(show_spinner=False)
def load_engine(db_path: str) -> DatabaseCostingEngine:
    return DatabaseCostingEngine(db_path)


def rebuild_database_from_workbook(db_path: Path, workbook_source) -> None:
    temp_db = db_path.with_suffix(db_path.suffix + ".rebuild")
    if temp_db.exists():
        temp_db.unlink()
    db = CostingDatabase(temp_db)
    try:
        db.import_workbook(workbook_source)
    finally:
        db.close()
    temp_db.replace(db_path)
    load_engine.clear()


def safe_index(options, value, default=0):
    """Find a default index robustly, including 1000 vs 1000.0 text/number cases."""
    if value is None:
        return default
    target_text = str(value).strip()
    try:
        target_num = float(str(value).replace(",", "").replace("g", ""))
    except Exception:
        target_num = None
    for idx, opt in enumerate(options):
        opt_text = str(opt).strip()
        if opt_text == target_text:
            return idx
        if target_num is not None:
            try:
                opt_num = float(str(opt).replace(",", "").replace("g", ""))
                if abs(opt_num - target_num) < 1e-9:
                    return idx
            except Exception:
                pass
    return default


def fmt_currency(value):
    if value is None:
        return "—"
    return f"₹{float(value):,.2f}"


def fmt_pct(value):
    if value is None:
        return "—"
    return f"{float(value) * 100:.1f}%"


def style_status(status: str):
    status = status or ""
    if status == "Loss":
        st.error("Status: Loss")
    elif status == "Low Margin":
        st.warning("Status: Low Margin")
    elif status == "Good":
        st.success("Status: Good")
    else:
        st.info(f"Status: {status}")


# Create default DB on first run.
ensure_database(DEFAULT_DB, DEFAULT_WORKBOOK)
active_db = DEFAULT_DB

with st.sidebar:
    st.header("Database")
    st.info("Using SQLite database generated from Excel")

    backup_dir = DATA_DIR / "backups"
    backup_dir.mkdir(exist_ok=True)
    if st.button("Backup current database"):
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = backup_dir / f"kusha_costing_backup_{stamp}.sqlite"
        shutil.copy2(active_db, backup_path)
        st.success(f"Backup saved: {backup_path.name}")

    backups = sorted(backup_dir.glob("*.sqlite"), reverse=True)
    if backups:
        with st.expander("Restore database backup"):
            selected_backup = st.selectbox("Choose backup", [b.name for b in backups])
            st.warning("Restoring replaces the current SQLite database. Excel is not changed.")
            if st.button("Restore selected backup", type="secondary"):
                src = backup_dir / selected_backup
                shutil.copy2(src, active_db)
                load_engine.clear()
                st.success(f"Restored backup: {selected_backup}. Refreshing app...")
                st.rerun()

    with st.expander("Rebuild database from bundled Excel (destructive)"):
        st.warning(
            "This DISCARDS all edits made in the app (MRP, products, recipes, mappings) "
            "and rebuilds from the bundled Excel file. The SQLite database is normally the "
            "source of truth — only rebuild to start over from the original workbook."
        )
        confirm_rebuild = st.checkbox("I understand this erases in-app changes", key="confirm_rebuild")
        if st.button("Rebuild now", disabled=not confirm_rebuild):
            rebuild_database_from_workbook(DEFAULT_DB, DEFAULT_WORKBOOK)
            st.success("Database rebuilt from bundled Excel. Please refresh if values look cached.")

    uploaded = st.file_uploader("Import updated workbook into database (.xlsx)", type=["xlsx"])
    if uploaded is not None:
        upload_db = DATA_DIR / "kusha_costing_uploaded.sqlite"
        rebuild_database_from_workbook(upload_db, uploaded.getvalue())
        active_db = upload_db
        st.success("Using database imported from uploaded workbook")

    engine = load_engine(str(active_db))
    engine.ensure_v5_schema()
    engine.ensure_v6_schema()

    check = engine.database_check()
    meta = check.get("meta", {})
    if meta.get("last_import_source"):
        st.caption(f"Imported from: {meta.get('last_import_source')}")

    st.divider()
    st.header("Settings")
    use_excel_misc = st.checkbox(
        "Use product-wise miscellaneous % from Production Cost",
        value=True,
        help="Recommended. Uses the % in Production Cost column J for each product. Turn off only for what-if testing.",
    )
    misc_pct_input = st.number_input(
        "Override Miscellaneous %",
        min_value=0.0,
        max_value=100.0,
        value=10.0,
        step=0.5,
        disabled=use_excel_misc,
        help="Used only when product-wise miscellaneous % is turned off.",
    ) / 100
    misc_pct_arg = None if use_excel_misc else misc_pct_input

    st.divider()
    st.header("Validation")
    if st.button("Validate imported Output Sheet"):
        try:
            validation = engine.validate_output_sheet()
            if validation["ok"] is True:
                st.success("Database calculation matches imported Output Sheet.")
            elif validation["ok"] is False:
                st.error("Database calculation mismatch.")
            else:
                st.warning("Could not compare expected amount.")
            st.json(validation)
        except Exception as exc:
            st.error(f"Validation failed: {exc}")


def calculator_tab():
    defaults = engine.default_output_inputs()
    products = engine.product_list()
    vendors = engine.vendor_options()
    sale_types = engine.sale_type_options()
    shipping_packs = engine.shipping_pack_options()

    left, right = st.columns([0.9, 1.4], gap="large")

    with left:
        st.subheader("Inputs")
        if not products:
            st.error("No products are available. Rebuild the database from a valid costing workbook.")
            return
        product = st.selectbox("Item", products, index=safe_index(products, defaults.get("item")))

        try:
            source = engine.source_for_product(product)
        except Exception:
            source = str(defaults.get("source") or "")
        st.text_input("Source", value=source, disabled=True)

        # Vendor is selected before size so the app can show only product/vendor-valid sizes.
        vendor = st.selectbox("Vendor", vendors, index=safe_index(vendors, defaults.get("vendor")))

        shipping_pack = st.selectbox(
            "Packing Material for Shipping",
            shipping_packs,
            index=safe_index(shipping_packs, defaults.get("shipping_pack")),
        )

        valid_sizes = engine.size_options_for_product(product, vendor)
        if not valid_sizes:
            st.error(
                "This product has no complete size and packaging mapping for the selected vendor. "
                "Complete it in Master Data Center → Packaging Mapping."
            )
            return
        size = st.selectbox("Size in grams", valid_sizes, index=safe_index(valid_sizes, defaults.get("size_g")))
        sale_type = st.selectbox("Type", sale_types, index=safe_index(sale_types, defaults.get("sale_type")))
        cost_modes = engine.cost_mode_options()
        default_cost_mode = cost_modes[1] if sale_type == "Wholesale" else cost_modes[0]
        cost_mode = st.selectbox("Cost Mode", cost_modes, index=safe_index(cost_modes, default_cost_mode))

    with right:
        st.subheader("Decision Output")
        try:
            result = engine.calculate_pricing(
                item=product,
                source=source,
                shipping_pack=shipping_pack,
                size_g=size,
                sale_type=sale_type,
                vendor=vendor,
                misc_pct=misc_pct_arg,
                cost_mode=cost_mode,
            )
            cost = result.cost

            # Show only the selected cost mode to avoid confusion between the two internal costing outputs.
            selected_cost_label = result.cost_mode
            metric_cols = st.columns(4)
            metric_cols[0].metric(selected_cost_label, fmt_currency(result.selected_cost))
            metric_cols[1].metric("MRP", fmt_currency(result.mrp))
            metric_cols[2].metric("Profit", fmt_currency(result.profit))
            metric_cols[3].metric("Margin %", fmt_pct(result.margin_pct))

            style_status(result.status)
            st.caption(result.status_reason)

            comparison_cost = engine.expected_production_cost_for(product, size, cost_mode)
            if comparison_cost is not None:
                selected_cost = result.selected_cost or cost.total_cost_with_new_shipping
                diff = selected_cost - comparison_cost
                if abs(diff) < 0.01:
                    st.success(f"Matches imported Production Cost value for selected mode: {fmt_currency(comparison_cost)}")
                else:
                    st.warning(
                        f"Calculated cost differs from the bundled workbook value by {fmt_currency(diff)}. "
                        "The app uses the consistent Version 8.3 formula; the difference can also reflect "
                        "Type/Vendor/Shipping Pack selections or an older cached workbook formula."
                    )

            breakdown_rows = [
                ("Raw Cost", cost.raw_cost),
                ("Product Packaging Cost", cost.packaging_cost),
                ("Sticker / Label Cost", cost.sticker_cost),
                ("Labour Cost", cost.labour_cost),
                ("Storage Cost", cost.storage_cost),
                ("Shipping Packing Cost", cost.shipping_packing_cost),
                ("New Shipping / Courier Cost", cost.new_shipping_cost),
                ("Miscellaneous Cost - Full/D2C", cost.miscellaneous_cost),
                ("Final Total Cost incl. New Shipping", cost.total_cost_with_new_shipping),
                ("Miscellaneous Cost - Wholesale", cost.wholesaler_miscellaneous_cost),
                ("Wholesaler Cost excl. Courier Shipping", cost.wholesaler_cost_excluding_courier_shipping),
            ]
            df = pd.DataFrame(breakdown_rows, columns=["Component", "Amount"])
            df["% of Final Cost"] = df["Amount"] / cost.total_cost_with_new_shipping

            st.dataframe(
                df.style.format({"Amount": "₹{:,.2f}", "% of Final Cost": "{:.1%}"}),
                hide_index=True,
                use_container_width=True,
            )

            with st.expander("Calculation details from database"):
                st.json(
                    {
                        "Item": cost.item,
                        "Source": cost.source,
                        "Size (g)": cost.size_g,
                        "Type": cost.sale_type,
                        "Vendor": cost.vendor,
                        "Shipping Pack": cost.shipping_pack,
                        "Landed Rate / g": cost.landed_rate_per_g,
                        "Product Packaging": cost.product_packaging_name,
                        "Packaging Required Qty": cost.packaging_required_qty,
                        "Packaging Rate": cost.packaging_rate,
                        "MRP Source": "SQLite table imported from New Cost sheet",
                        "Cost Mode": result.cost_mode,
                        "Selected Cost": result.selected_cost,
                        "Full/D2C Miscellaneous": cost.miscellaneous_cost,
                        "Wholesale Miscellaneous": cost.wholesaler_miscellaneous_cost,
                    }
                )

            out_rows = df.copy()
            summary = pd.DataFrame(
                [
                    ["Selected Cost", result.selected_cost, None],
                    ["Cost Mode", result.cost_mode, None],
                    ["MRP", result.mrp, None],
                    ["Profit", result.profit, None],
                    ["Margin %", result.margin_pct, None],
                    ["Status", result.status, None],
                ],
                columns=["Component", "Amount", "% of Final Cost"],
            )
            export_df = pd.concat([out_rows, summary], ignore_index=True)
            csv = export_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                "Download cost + margin CSV",
                data=csv,
                file_name=f"{product}_{size}g_cost_margin.csv".replace("/", "-"),
                mime="text/csv",
            )

        except Exception as exc:
            st.error("Could not calculate cost for the selected combination.")
            st.exception(exc)


def reports_tab():
    st.subheader("Portfolio Reports")
    report_cost_mode = st.selectbox("Analyze using cost mode", engine.cost_mode_options(), key="report_cost_mode")
    rows = engine.sku_report_from_new_cost(cost_mode=report_cost_mode)
    if not rows:
        st.warning("No report data found in database. Rebuild/import the database from your workbook.")
        return

    df = pd.DataFrame(rows)
    total_skus = len(df)
    loss_count = int((df["Status"] == "Loss").sum())
    low_count = int((df["Status"] == "Low Margin").sum())
    good_count = int((df["Status"] == "Good").sum())
    avg_margin = df["Margin %"].dropna().mean()

    kpis = st.columns(5)
    kpis[0].metric("Total SKU Variations", f"{total_skus}")
    kpis[1].metric("Loss Making", f"{loss_count}")
    kpis[2].metric("Low Margin", f"{low_count}")
    kpis[3].metric("Good", f"{good_count}")
    kpis[4].metric("Avg Margin", fmt_pct(avg_margin))

    status_filter = st.multiselect(
        "Filter by status",
        options=["Loss", "Low Margin", "Good", "MRP Missing", "Invalid MRP", "Invalid Cost", "Setup Incomplete"],
        default=["Loss", "Low Margin"],
    )
    size_filter = st.multiselect(
        "Filter by size",
        options=sorted(df["Size (g)"].unique().tolist()),
        default=sorted(df["Size (g)"].unique().tolist()),
    )

    filtered = df[df["Status"].isin(status_filter) & df["Size (g)"].isin(size_filter)].copy()
    filtered = filtered.sort_values(["Profit", "Margin %"], ascending=[True, True])
    display_cols = ["Item", "Size (g)", "Final Cost", "MRP", "Profit", "Margin %", "Status"]

    st.dataframe(
        filtered[display_cols].style.format(
            {"Final Cost": "₹{:,.2f}", "MRP": "₹{:,.2f}", "Profit": "₹{:,.2f}", "Margin %": "{:.1%}"}
        ),
        hide_index=True,
        use_container_width=True,
    )

    st.download_button(
        "Download filtered report CSV",
        data=filtered[display_cols].to_csv(index=False).encode("utf-8"),
        file_name="kusha_costing_report_v8.3.csv",
        mime="text/csv",
    )

    with st.expander("Top 10 worst margin variations"):
        worst = df.sort_values("Margin %", ascending=True).head(10)
        st.dataframe(
            worst[display_cols].style.format(
                {"Final Cost": "₹{:,.2f}", "MRP": "₹{:,.2f}", "Profit": "₹{:,.2f}", "Margin %": "{:.1%}"}
            ),
            hide_index=True,
            use_container_width=True,
        )


def database_check_tab():
    st.subheader("Database Check")
    st.markdown(
        """
This page checks the SQLite database that was imported from Excel. It does not edit Excel or the database.
"""
    )
    check = engine.database_check()
    st.write("Import metadata")
    st.json(check.get("meta", {}))

    counts = pd.DataFrame([{"Table": k, "Rows": v} for k, v in check.get("counts", {}).items()])
    st.dataframe(counts, hide_index=True, use_container_width=True)

    st.markdown("### Cost reconciliation — app formula vs imported workbook")
    st.caption(
        "Confirms how the app's calculated cost compares to the cost stored in the original Excel, "
        "so you can trust the app before retiring the spreadsheet. The app uses the consistent "
        "Version 8.3 formula; differences are shown per product, never hidden."
    )
    try:
        rec_rows = engine.cost_reconciliation_rows()
        if rec_rows:
            rec_df = pd.DataFrame(rec_rows)
            total = len(rec_df)
            matches = int(rec_df["Matches"].sum())
            mc1, mc2, mc3 = st.columns(3)
            mc1.metric("Rows compared", f"{total}")
            mc2.metric("Match workbook", f"{matches}")
            mc3.metric("Differ", f"{total - matches}")
            only_diffs = st.checkbox("Show only rows that differ", value=True, key="recon_only_diffs")
            view = rec_df[~rec_df["Matches"]] if only_diffs else rec_df
            money_cols = [c for c in ["App Full", "Excel Full", "Diff Full", "App Wholesale", "Excel Wholesale", "Diff Wholesale"] if c in view.columns]
            st.dataframe(
                view.style.format({c: "₹{:,.2f}" for c in money_cols}, na_rep="—"),
                hide_index=True,
                use_container_width=True,
            )
            st.download_button(
                "Download reconciliation CSV",
                data=rec_df.to_csv(index=False).encode("utf-8"),
                file_name="kusha_cost_reconciliation.csv",
                mime="text/csv",
            )
            if total - matches > 0:
                st.info(
                    "Differences here are expected: at 1000g the app includes storage cost inside the "
                    "overhead base, which the original spreadsheet handled slightly differently. The gap is "
                    "small and systematic. Use the app value as the single source of truth going forward."
                )
    except Exception as exc:
        st.warning(f"Could not build reconciliation: {exc}")

    validation = engine.validate_output_sheet()
    if validation["ok"] is True:
        st.success("Sample Output Sheet validation passed.")
    elif validation["ok"] is False:
        st.error("Sample Output Sheet validation mismatch.")
    else:
        st.warning("Sample Output Sheet validation could not be compared.")
    st.json(validation)



def _mrp_changed(new_value, old_value):
    def _norm(v):
        try:
            if v is None or (isinstance(v, float) and pd.isna(v)):
                return None
            return round(float(v), 4)
        except Exception:
            return None
    return _norm(new_value) != _norm(old_value)


def mrp_pricing_editor():
    st.markdown("### MRP / selling price")
    st.caption(
        "Set the selling price (MRP) for every product-size here — no spreadsheet needed. "
        "**Live Cost** is recalculated from current master data, so you can price directly against real cost."
    )
    cmode = st.selectbox("Cost basis for live cost & margin", engine.cost_mode_options(), key="mrp_cost_mode")
    search = st.text_input("Search product", key="mrp_search", placeholder="Example: Black Cardamom")
    rows = engine.mrp_editor_rows(search=search, cost_mode=cmode)

    if rows:
        df = pd.DataFrame(rows)
        original = {(r["item_norm"], r["Size (g)"]): r["MRP"] for r in rows}
        df_display = df.copy()
        df_display["Margin %"] = df_display["Margin %"].apply(
            lambda v: v * 100 if v is not None and not pd.isna(v) else v
        )
        edited = st.data_editor(
            df_display,
            hide_index=True,
            use_container_width=True,
            disabled=["item_norm", "Item", "Size (g)", "Live Cost", "Margin %", "Status"],
            column_config={
                "item_norm": None,
                "Item": "Product",
                "Size (g)": st.column_config.NumberColumn("Size (g)", format="%d"),
                "Live Cost": st.column_config.NumberColumn("Live Cost", format="₹%.2f"),
                "MRP": st.column_config.NumberColumn("MRP / Selling Price", format="₹%.2f", min_value=0.0),
                "Margin %": st.column_config.NumberColumn("Margin %", format="%.1f%%"),
                "Status": "Status",
            },
            key="mrp_editor",
        )
        if st.button("Save MRP / selling prices", type="primary"):
            changed = 0
            for _, r in edited.iterrows():
                key = (r["item_norm"], r["Size (g)"])
                if _mrp_changed(r["MRP"], original.get(key)):
                    value = None if pd.isna(r["MRP"]) else r["MRP"]
                    engine.upsert_mrp_variation(r["Item"], r["Size (g)"], value)
                    changed += 1
            st.success(f"Saved {changed} selling-price change(s).")
            st.rerun()
    else:
        st.info("No priced variations match this search. Add one below.")

    with st.expander("Add / set MRP for a product-size"):
        products = engine.product_list()
        c1, c2, c3 = st.columns(3)
        prod = c1.selectbox("Product", products, key="mrp_add_product")
        size_opts = engine.size_options_for_product(prod) or engine.size_options()
        size = c2.selectbox("Size (g)", size_opts, key="mrp_add_size")
        new_mrp = c3.number_input("MRP / selling price", min_value=0.0, step=1.0, key="mrp_add_value")
        if st.button("Save MRP"):
            try:
                engine.upsert_mrp_variation(prod, size, new_mrp)
                st.success(f"MRP set for {prod} {int(size)}g.")
                st.rerun()
            except Exception as exc:
                st.error(f"Could not set MRP: {exc}")


def master_data_center_tab():
    st.subheader("Master Data Center")
    st.info(
        "Version 8.3 is SQLite-first: edits are saved to the app database. Excel remains available as backup/import/export source."
    )

    tabs = st.tabs([
        "MRP & Selling Price",
        "Raw/Product + GST",
        "Packaging List",
        "Packaging Mapping",
        "Shipping Logic",
        "Storage & Basic Costs",
    ])

    with tabs[0]:
        mrp_pricing_editor()

    with tabs[1]:
        st.markdown("### Raw/product rates with category and item-level GST")
        st.caption("Wholesale is treated as ex-GST. Retail can be maintained as with-GST for D2C. GST is shown separately and is item-level.")
        cats = ["All"] + engine.item_categories()
        cat = st.selectbox("Category filter", cats, key="v5_rate_category")
        search = st.text_input("Search material/product", key="v5_rate_search", placeholder="Example: Cloves, Black Pepper, Chaat Masala")
        rows = engine.list_master_rate_rows_v5(search=search, category=cat, limit=500)
        if rows:
            df = pd.DataFrame(rows)
            edited = st.data_editor(
                df,
                hide_index=True,
                use_container_width=True,
                disabled=["item_norm", "row_no", "name", "source_or_type"],
                column_config={
                    "item_norm": None,
                    "row_no": "DB Row",
                    "name": "Name",
                    "category": st.column_config.SelectboxColumn("Category", options=engine.item_categories()+["Other / Review"]),
                    "source_or_type": "Source / Type",
                    "gst_pct": st.column_config.NumberColumn("GST %", min_value=0.0, max_value=100.0, step=0.5),
                    "wholesale_ex_gst": st.column_config.NumberColumn("Wholesale ex-GST", format="₹%.4f"),
                    "retail_with_gst": st.column_config.NumberColumn("Retail with GST", format="₹%.4f"),
                    "active": st.column_config.CheckboxColumn("Active"),
                },
                key="v5_rates_editor",
            )
            if st.button("Save raw/product rates + GST", type="primary"):
                for _, r in edited.iterrows():
                    engine.update_item_catalog_row(str(r["item_norm"]), str(r["category"]), r["gst_pct"], bool(r["active"]))
                    if pd.notna(r.get("row_no")):
                        engine.update_master_value_by_row(int(r["row_no"]), 21, r["wholesale_ex_gst"])
                        engine.update_master_value_by_row(int(r["row_no"]), 22, r["retail_with_gst"])
                st.success("Saved rates, categories and GST to SQLite.")
                st.rerun()
        else:
            st.warning("No rows found.")

    with tabs[2]:
        st.markdown("### Packaging material dropdown list")
        st.caption("This list controls the dropdown options available in packaging mapping. Add/delete here first, then map it to product variations.")
        col_a, col_b = st.columns([1,1])
        with col_a:
            vendor_filter = st.selectbox("Vendor", ["All", "Maruthi Plastics", "Swiss Pac", ""], key="v5_pack_vendor_filter")
        with col_b:
            search_pack = st.text_input("Search packaging material", key="v5_pack_search")
        rows = engine.list_packaging_materials(search=search_pack, vendor=vendor_filter, include_inactive=True, limit=500)
        if rows:
            df = pd.DataFrame(rows)
            edited = st.data_editor(
                df,
                hide_index=True,
                use_container_width=True,
                disabled=["material_norm", "source_row_no"],
                column_config={
                    "material_norm": None,
                    "material_name": "Material Name",
                    "vendor": st.column_config.SelectboxColumn("Vendor", options=["Maruthi Plastics", "Swiss Pac", "", "Other"]),
                    "category": st.column_config.SelectboxColumn("Category", options=["Packaging Material", "Shipping Packing Material", "Sticker / Label", "Other"]),
                    "wholesale_ex_gst": st.column_config.NumberColumn("Wholesale ex-GST", format="₹%.4f"),
                    "retail_with_gst": st.column_config.NumberColumn("Retail with GST", format="₹%.4f"),
                    "gst_pct": st.column_config.NumberColumn("GST %", min_value=0.0, max_value=100.0, step=0.5),
                    "active": st.column_config.CheckboxColumn("Active"),
                },
                key="v5_packaging_list_editor",
            )
            if st.button("Save packaging material list", type="primary"):
                for _, r in edited.iterrows():
                    engine.upsert_packaging_material(
                        r["material_name"], r.get("vendor") or "", r.get("category") or "Packaging Material",
                        r.get("wholesale_ex_gst"), r.get("retail_with_gst"), r.get("gst_pct"), bool(r.get("active", True))
                    )
                st.success("Packaging material list saved.")
                st.rerun()
        else:
            st.info("No packaging materials found for this filter.")

        with st.expander("Add a new packaging material"):
            n1, n2, n3 = st.columns(3)
            new_name = n1.text_input("Material name", key="v5_new_pack_name")
            new_vendor = n2.selectbox("Vendor", ["Maruthi Plastics", "Swiss Pac", "", "Other"], key="v5_new_pack_vendor")
            new_cat = n3.selectbox("Category", ["Packaging Material", "Shipping Packing Material", "Sticker / Label", "Other"], key="v5_new_pack_cat")
            n4, n5, n6 = st.columns(3)
            new_wh = n4.number_input("Wholesale ex-GST", min_value=0.0, step=0.01, key="v5_new_pack_wh")
            new_retail = n5.number_input("Retail with GST", min_value=0.0, step=0.01, key="v5_new_pack_retail")
            new_gst = n6.number_input("GST %", min_value=0.0, max_value=100.0, value=18.0, step=0.5, key="v5_new_pack_gst")
            if st.button("Add packaging material"):
                engine.upsert_packaging_material(new_name, new_vendor, new_cat, new_wh, new_retail, new_gst, True)
                st.success("Packaging material added and made available in mapping dropdowns.")
                st.rerun()

    with tabs[3]:
        st.markdown("### Product packaging mapping — dropdown by product variation")
        st.caption("Dropdown shows packaging materials for the selected vendor. This controls which packaging is used for each product + size.")
        vendor_map = st.selectbox("Vendor mapping table", ["Maruthi Plastics", "Swiss Pac"], key="v5_mapping_vendor")
        table_name = "maruthi_packaging" if vendor_map == "Maruthi Plastics" else "swiss_packaging"
        options = engine.packaging_material_options(vendor=vendor_map, category="Packaging Material")
        options = sorted(set(options + ["", "NA", "None"]))
        item_filter = st.text_input("Filter product", key="v5_pack_mapping_filter", placeholder="Example: Black Cardamom")
        rows = engine.matrix_table_rows(table_name, item_filter=item_filter, limit=700)
        if rows:
            df = pd.DataFrame(rows)
            edited = st.data_editor(
                df,
                hide_index=True,
                use_container_width=True,
                disabled=["row_no", "col_no", "item", "size_g"],
                column_config={
                    "row_no": None,
                    "col_no": None,
                    "item": "Product",
                    "size_g": "Size (g)",
                    "value": st.column_config.SelectboxColumn("Packaging material", options=options),
                },
                key=f"v5_mapping_editor_{table_name}",
            )
            if st.button("Save packaging mapping", type="primary"):
                for _, r in edited.iterrows():
                    engine.update_matrix_value(table_name, int(r["row_no"]), int(r["col_no"]), r["value"])
                st.success("Packaging mapping saved.")
                st.rerun()
        else:
            st.warning("No mapping rows found. Try another filter.")

        st.markdown("### Packing quantity required")
        qty_filter = st.text_input("Filter product for quantity mapping", key="v5_qty_filter", placeholder="Example: Black Cardamom")
        qty_rows = engine.matrix_table_rows("packing_required", item_filter=qty_filter, limit=700)
        if qty_rows:
            qdf = pd.DataFrame(qty_rows)
            qedit = st.data_editor(
                qdf,
                hide_index=True,
                use_container_width=True,
                disabled=["row_no", "col_no", "item", "size_g"],
                column_config={"row_no": None, "col_no": None, "item": "Product", "size_g": "Size (g)", "value": st.column_config.NumberColumn("Qty required", format="%.4f")},
                key="v5_qty_editor",
            )
            if st.button("Save packing qty required", type="primary"):
                for _, r in qedit.iterrows():
                    engine.update_matrix_value("packing_required", int(r["row_no"]), int(r["col_no"]), r["value"])
                st.success("Packing quantity saved.")
                st.rerun()

    with tabs[4]:
        st.markdown("### Shipping logic")
        st.caption("Current model: weighted average of shipping zones, then converted into size-wise new shipping cost. This explains and edits your shipping calculation.")
        zdf = pd.DataFrame(engine.shipping_zone_rows())
        zedit = st.data_editor(
            zdf,
            hide_index=True,
            use_container_width=True,
            disabled=["zone_key"],
            column_config={
                "zone_key": None,
                "zone_name": "Zone",
                "cost_1kg": st.column_config.NumberColumn("1kg shipping cost", format="₹%.2f"),
                "weight_pct": st.column_config.NumberColumn("Order mix weight %", format="%.2f"),
            },
            key="v5_shipping_zones",
        )
        st.metric("Weighted 1kg shipping", fmt_currency(engine.weighted_shipping_1kg()))
        if st.button("Save zone weights"):
            engine.update_shipping_zones(zedit.to_dict("records"))
            st.success("Shipping zone model saved.")
            st.rerun()
        if st.button("Apply weighted model to size-wise new shipping cells", type="primary"):
            vals = engine.apply_weighted_shipping_to_cells()
            st.success("Updated new shipping cells: " + ", ".join([f"{k}={v:.2f}" for k,v in vals.items()]))
            st.rerun()

    with tabs[5]:
        st.markdown("### Storage, sticker and labour settings")
        setting_rows = [
            ("Storage: 1000g", "AF40"),
            ("Storage: 500g / 250g", "AF39"),
            ("Storage: 100g / 50g / 25g / other small sizes", "AF38"),
            ("New shipping: 1000g", "AB32"),
            ("New shipping: 500g", "AB33"),
            ("New shipping: 250g", "AB34"),
            ("New shipping: 100g", "AB35"),
            ("New shipping: 50g", "AB36"),
            ("New shipping: 25g", "AB37"),
            ("New shipping: 1g / other", "AB38"),
            ("Sticker cost - Wholesale", "V127"),
            ("Sticker cost - Retail", "W127"),
            ("Labour cost - Wholesale", "V111"),
            ("Labour cost - Retail", "W111"),
        ]
        cols = st.columns(2)
        edited_settings = {}
        for idx, (label, cell_ref) in enumerate(setting_rows):
            current = engine.cell_value("Master Data", cell_ref)
            try:
                current_float = float(current or 0)
            except Exception:
                current_float = 0.0
            with cols[idx % 2]:
                edited_settings[cell_ref] = st.number_input(label + f" ({cell_ref})", value=current_float, step=0.01, format="%.4f", key=f"v5_setting_{cell_ref}")
        if st.button("Save storage/shipping/basic settings", type="primary"):
            for cell_ref, value in edited_settings.items():
                engine.update_cell_value("Master Data", cell_ref, value)
            st.success("Settings saved.")
            st.rerun()


def bom_builder_tab():
    st.subheader("Masala / Blend Recipe Builder")
    st.info("Recipes are standardized per 1kg finished product. Imported recipes are visible immediately, but they do not change calculator costs until you approve them below.")
    products = engine.product_list()
    existing_recipes = engine.recipe_products()
    st.caption(f"{len(existing_recipes)} recipes available from the costing workbook/database.")
    mode = st.radio(
        "Recipe product",
        ["View/edit imported recipe", "Create recipe for product", "Create new product name"],
        horizontal=True,
    )
    if mode == "View/edit imported recipe":
        if not existing_recipes:
            st.warning("No recipes have been imported yet. Rebuild the database from the workbook in Admin Controls.")
            return
        product = st.selectbox("Masala / blend recipe", existing_recipes)
    elif mode == "Create recipe for product":
        product = st.selectbox("Finished product", products)
    else:
        product = st.text_input("New finished product name", placeholder="Example: Premium Biryani Masala")
    product = normalize(product) if 'normalize' in globals() else str(product).strip()
    header = engine.recipe_header(product) if product else None
    raw_options = [r['name'] for r in engine.list_master_rate_rows_v5(category='Raw Material', limit=2000)]
    if not raw_options:
        raw_options = engine.product_list()
    current = engine.recipe_ingredients(product) if product else []
    raw_options = sorted(set(raw_options + [r.get('ingredient_name', '') for r in current if r.get('ingredient_name')]))
    if current:
        df = pd.DataFrame(current).drop(columns=["id"], errors="ignore")
    else:
        df = pd.DataFrame([{"ingredient_name": "", "qty_g_per_kg": 0.0}])
    edited = st.data_editor(
        df,
        num_rows="dynamic",
        hide_index=True,
        use_container_width=True,
        column_config={
            "ingredient_name": st.column_config.SelectboxColumn("Ingredient", options=[""] + raw_options, required=False),
            "qty_g_per_kg": st.column_config.NumberColumn("Qty g per 1kg final product", min_value=0.0, step=0.1, format="%.4f"),
        },
        key=f"v5_recipe_editor_{product}",
    )
    overhead_default = float((header or {}).get('overhead_pct') or 0)
    use_for_costing_default = bool((header or {}).get('use_for_costing') or 0)
    controls = st.columns(2)
    with controls[0]:
        overhead_pct = st.number_input(
            "Recipe processing / energy & miscellaneous %",
            min_value=0.0,
            max_value=100.0,
            value=overhead_default,
            step=0.5,
            key=f"v5_recipe_overhead_{product}",
        )
    with controls[1]:
        use_for_costing = st.checkbox(
            "Use this verified recipe in calculator costing",
            value=use_for_costing_default,
            key=f"v5_recipe_use_costing_{product}",
        )
    notes = st.text_area(
        "Recipe notes",
        value=str((header or {}).get('notes') or ''),
        key=f"v5_recipe_notes_{product}",
    )
    recipe_total = float(pd.to_numeric(edited["qty_g_per_kg"], errors="coerce").fillna(0).sum()) if "qty_g_per_kg" in edited else 0.0
    st.caption(f"Recipe total: {recipe_total:,.1f}g per 1,000g finished product")
    if current and abs(recipe_total - 1000) > 0.1:
        st.warning("This source recipe does not total 1,000g. It remains excluded from calculator costing until corrected and saved.")
    if st.button("Save recipe", type="primary", disabled=not bool(product)):
        try:
            engine.save_recipe(product, edited.to_dict("records"), notes, overhead_pct, use_for_costing)
            if use_for_costing:
                st.success("Recipe saved and approved for calculator costing.")
            else:
                st.success("Recipe saved for reference; existing imported product rates remain active in the calculator.")
            st.rerun()
        except Exception as exc:
            st.error(f"Could not save recipe: {exc}")
    if product:
        recipe_cost = engine.recipe_cost_per_kg(product, "Wholesale")
        if recipe_cost:
            metrics = st.columns(3)
            metrics[0].metric("Ingredient cost / kg", fmt_currency(recipe_cost['ingredient_cost_per_kg']))
            metrics[1].metric("Processing / energy / misc", fmt_currency(recipe_cost['overhead_cost']))
            metrics[2].metric("Recipe cost / kg", fmt_currency(recipe_cost['cost_per_kg']))
            st.caption(f"Calculated recipe rate: ₹{recipe_cost['rate_per_g']:.4f} per gram, including {recipe_cost['overhead_pct']:.1f}% recipe overhead.")
            with st.expander("Ingredient cost breakdown"):
                st.dataframe(pd.DataFrame(recipe_cost['details']).style.format({'Rate / g':'₹{:.4f}', 'Cost':'₹{:,.2f}'}), hide_index=True, use_container_width=True)


def transport_and_gst_tab():
    st.subheader("Raw Material Source + Transportation + GST")
    st.info("Transport is separated into supplier packing, farmer-to-transporter, VRL state-to-Mumbai, and local Mumbai transport. Choose Direct when the vendor sends material directly to your office.")
    search = st.text_input("Search raw material source", key="v5_transport_search", placeholder="Example: Cloves")
    rows = engine.transport_source_rows(search=search, limit=500)
    if rows:
        df = pd.DataFrame(rows)
    else:
        df = pd.DataFrame(columns=["id","material_name","vendor_name","transport_method","base_material_cost_ex_gst","supplier_packing_cost","farmer_to_transporter_cost","vrl_state_to_mumbai_cost","mumbai_local_transport_cost","direct_transport_cost","quantity_kg","gst_pct","active","notes","transport_total","landed_cost_per_g"])
    edited = st.data_editor(
        df,
        num_rows="dynamic",
        hide_index=True,
        use_container_width=True,
        disabled=["transport_total", "landed_cost_per_g"],
        column_config={
            "id": "ID",
            "material_name": st.column_config.TextColumn("Material"),
            "vendor_name": st.column_config.TextColumn("Vendor/Farmer"),
            "transport_method": st.column_config.SelectboxColumn("Transport method", options=["VRL", "Direct"]),
            "base_material_cost_ex_gst": st.column_config.NumberColumn("Material cost ex-GST", format="₹%.2f"),
            "supplier_packing_cost": st.column_config.NumberColumn("Manufacturer/Farmer packing", format="₹%.2f"),
            "farmer_to_transporter_cost": st.column_config.NumberColumn("Farmer → transporter", format="₹%.2f"),
            "vrl_state_to_mumbai_cost": st.column_config.NumberColumn("VRL state → Mumbai", format="₹%.2f"),
            "mumbai_local_transport_cost": st.column_config.NumberColumn("Mumbai VRL → office", format="₹%.2f"),
            "direct_transport_cost": st.column_config.NumberColumn("Direct transport", format="₹%.2f"),
            "quantity_kg": st.column_config.NumberColumn("Quantity kg", min_value=0.0, format="%.3f"),
            "gst_pct": st.column_config.NumberColumn("GST %", min_value=0.0, max_value=100.0, step=0.5),
            "active": st.column_config.CheckboxColumn("Use for costing"),
            "transport_total": st.column_config.NumberColumn("Transport total", format="₹%.2f"),
            "landed_cost_per_g": st.column_config.NumberColumn("Landed cost/g", format="₹%.4f"),
        },
        key="v5_transport_editor",
    )
    if st.button("Save raw material source costs", type="primary"):
        try:
            for _, r in edited.iterrows():
                if str(r.get("material_name", "")).strip():
                    engine.upsert_transport_source(r.to_dict())
            st.success("Raw material source/transport records saved.")
            st.rerun()
        except Exception as exc:
            st.error(f"Could not save transport data: {exc}")


def manage_products_panel():
    st.markdown("### Manage existing products")
    st.caption("Edit attributes, add/remove sizes, or discontinue a product. All changes save to the app database.")
    search = st.text_input("Search product", key="mp_search", placeholder="Example: Cloves")
    rows = engine.list_products_admin(search=search)
    if not rows:
        st.info("No products found for this search.")
        return
    df = pd.DataFrame(rows)
    st.dataframe(df.drop(columns=["item_norm"]), hide_index=True, use_container_width=True)

    product_names = [r["Product"] for r in rows]
    selected = st.selectbox("Select product to edit", product_names, key="mp_select")
    rec = next((r for r in rows if r["Product"] == selected), None)
    if not rec:
        return
    item_norm = rec["item_norm"]

    st.markdown("#### Edit core attributes")
    cat_opts = engine.item_categories() + [
        "Raw Material", "Masala / Blend / Finished Product", "Pickle / Finished Product",
        "Packaging Material", "Other / Review",
    ]
    cat_opts = sorted(set([c for c in cat_opts if c]))
    e1, e2, e3 = st.columns(3)
    new_cat = e1.selectbox("Category", cat_opts, index=safe_index(cat_opts, rec.get("Category")), key="mp_cat")
    new_source = e2.text_input("Source / Type", value=str(rec.get("Source / Type") or ""), key="mp_source")
    new_gst = e3.number_input("GST %", min_value=0.0, max_value=100.0, value=float(rec.get("GST %") or 0), step=0.5, key="mp_gst")
    e4, e5, e6 = st.columns(3)
    new_vendor = e4.selectbox("Default vendor", engine.vendor_options(), key="mp_vendor")
    new_ship = e5.selectbox("Default shipping pack", engine.shipping_pack_options(), key="mp_ship")
    new_sale = e6.selectbox("Default type", engine.sale_type_options(), key="mp_sale")
    cur_misc = engine.misc_pct_for_product(selected) * 100
    new_misc = st.number_input(
        "Miscellaneous % (per product)", min_value=0.0, max_value=100.0,
        value=float(round(cur_misc, 2)), step=0.5, key="mp_misc",
    )
    if st.button("Save product attributes", type="primary", key="mp_save_core"):
        try:
            engine.update_product_core(
                item_norm, category=new_cat, source_or_type=new_source, gst_pct=new_gst,
                default_vendor=new_vendor, default_shipping_pack=new_ship, sale_type=new_sale, misc_pct=new_misc,
            )
            st.success("Product attributes saved.")
            st.rerun()
        except Exception as exc:
            st.error(f"Could not save: {exc}")

    st.divider()
    st.markdown("#### Sizes")
    cur_sizes = engine.size_options_for_product(selected) or []
    st.write("Current sizes:", ", ".join(str(s) for s in cur_sizes) or "none mapped")
    a1, a2, a3, a4 = st.columns(4)
    add_size = a1.number_input("Add size (g)", min_value=0.0, step=1.0, key="mp_add_size")
    add_vendor = a2.selectbox("Vendor", engine.vendor_options(), key="mp_add_vendor")
    add_pack = a3.selectbox(
        "Packaging material",
        [""] + engine.packaging_material_options(vendor=add_vendor, category="Packaging Material"),
        key="mp_add_pack",
    )
    add_qty = a4.number_input("Packing qty", min_value=0.0, value=1.0, step=0.1, key="mp_add_qty")
    if st.button("Add size", key="mp_add_size_btn"):
        try:
            engine.add_product_size(
                selected, add_size, vendor=add_vendor, packaging_material=add_pack,
                packing_required_qty=add_qty, sale_type=new_sale,
            )
            st.success(f"Added {int(add_size)}g to {selected}.")
            st.rerun()
        except Exception as exc:
            st.error(f"Could not add size: {exc}")
    if cur_sizes:
        r1, r2 = st.columns([1, 1])
        rem_size = r1.selectbox("Remove size (g)", cur_sizes, key="mp_rem_size")
        if r2.button("Remove selected size", key="mp_rem_btn"):
            try:
                engine.remove_product_size(selected, rem_size)
                st.success(f"Removed {int(rem_size)}g from {selected}.")
                st.rerun()
            except Exception as exc:
                st.error(f"Could not remove size: {exc}")

    st.divider()
    with st.expander("⚠️ Discontinue / delete product"):
        st.warning(
            f"This permanently removes '{selected}' and all of its sizes, packaging mappings, "
            "recipe and pricing from the app database."
        )
        confirm = st.checkbox(f"I want to delete '{selected}'", key="mp_del_confirm")
        if st.button("Delete product", disabled=not confirm, key="mp_del_btn"):
            try:
                engine.delete_product(selected)
                st.success(f"Deleted {selected}.")
                st.rerun()
            except Exception as exc:
                st.error(f"Could not delete product: {exc}")


def admin_controls_tab():
    st.subheader("Admin Controls")
    st.info("Version 6 adds controlled product creation, database backup/restore, and audit history. Use this before replacing Excel fully.")

    sub = st.tabs(["Add Product Skeleton", "Manage Products", "Audit Log", "Database Backup Export"])

    with sub[0]:
        st.markdown("### Add a new product skeleton")
        st.caption("This creates database rows so the product can appear in Calculator and mapping screens. After saving, complete packaging mapping, MRP, transport/source, and recipe if needed.")
        c1, c2 = st.columns(2)
        with c1:
            new_product = st.text_input("Product name", key="v6_new_product_name")
            category_options = engine.item_categories() + ["Raw Material", "Masala / Blend / Finished Product", "Pickle / Finished Product", "Packaging Material", "Other / Review"]
            category_options = sorted(set([x for x in category_options if x]))
            new_category = st.selectbox("Category", category_options, index=safe_index(category_options, "Raw Material"), key="v6_new_product_category")
            source_type = st.text_input("Source / Type", value="", placeholder="Supplier name OR In House Production", key="v6_new_product_source")
            sale_type = st.selectbox("Default type", engine.sale_type_options(), key="v6_new_product_sale_type")
        with c2:
            selected_sizes = st.multiselect("Size variations to create", engine.size_options(), default=[100], key="v6_new_product_sizes")
            default_vendor = st.selectbox("Default packaging vendor", engine.vendor_options(), key="v6_new_product_vendor")
            default_shipping_pack = st.selectbox("Default shipping packing", engine.shipping_pack_options(), index=safe_index(engine.shipping_pack_options(), "Five Ply Box"), key="v6_new_product_ship_pack")
            default_packaging = st.selectbox("Default product packaging", [""] + engine.packaging_material_options(vendor=default_vendor, category="Packaging Material"), key="v6_new_product_packaging")
        c3, c4, c5, c6 = st.columns(4)
        wh = c3.number_input("Wholesale ex-GST rate/g", min_value=0.0, step=0.0001, format="%.4f", key="v6_new_product_wh")
        retail = c4.number_input("Retail with-GST rate/g", min_value=0.0, step=0.0001, format="%.4f", key="v6_new_product_retail")
        gst = c5.number_input("GST %", min_value=0.0, max_value=100.0, step=0.5, key="v6_new_product_gst")
        pack_qty = c6.number_input("Packing qty required", min_value=0.0, value=1.0, step=0.1, key="v6_new_product_pack_qty")

        if st.button("Create product skeleton", type="primary"):
            try:
                resolved_source = source_type
                if not resolved_source and "Masala" in new_category:
                    resolved_source = "In House Production"
                engine.create_product_v6(
                    product_name=new_product,
                    category=new_category,
                    source_or_type=resolved_source,
                    wholesale_ex_gst=wh,
                    retail_with_gst=retail,
                    gst_pct=gst,
                    sizes=selected_sizes,
                    default_vendor=default_vendor,
                    default_shipping_pack=default_shipping_pack,
                    packing_required_qty=pack_qty,
                    default_packaging_material=default_packaging,
                    sale_type=sale_type,
                )
                st.success("Product skeleton created. Now complete packaging mapping, MRP and recipe/source data.")
                st.rerun()
            except Exception as exc:
                st.error(f"Could not create product: {exc}")

    with sub[1]:
        manage_products_panel()

    with sub[2]:
        st.markdown("### Change history / audit log")
        search = st.text_input("Search audit log", key="v6_audit_search")
        rows = engine.audit_log_rows(search=search, limit=500)
        if rows:
            df = pd.DataFrame(rows)
            st.dataframe(df, hide_index=True, use_container_width=True)
            st.download_button("Download audit log CSV", df.to_csv(index=False).encode("utf-8"), "kusha_audit_log.csv", "text/csv")
        else:
            st.info("No audit entries yet. Edits made from Version 6 onwards will appear here.")
        with st.expander("Danger zone"):
            if st.button("Clear audit log"):
                engine.clear_audit_log()
                st.success("Audit log cleared.")
                st.rerun()

    with sub[3]:
        st.markdown("### Database backup export")
        st.caption("Download the current SQLite database to save/share with a developer.")
        try:
            db_bytes = Path(active_db).read_bytes()
            st.download_button("Download current SQLite database", db_bytes, file_name="kusha_costing_current.sqlite", mime="application/octet-stream")
        except Exception as exc:
            st.error(f"Could not prepare database download: {exc}")


def validation_center_tab():
    st.subheader("Validation Center")
    st.info("This page flags missing mappings, missing MRPs, missing recipe setup, inactive/blank transport rows, and other admin issues.")
    issues = engine.validation_issues()
    if not issues:
        st.success("No validation issues found.")
        return
    df = pd.DataFrame(issues)
    sev_order = {"High": 0, "Medium": 1, "Low": 2}
    df["_sort"] = df["Severity"].map(sev_order).fillna(9)
    df = df.sort_values(["_sort", "Area", "Item / Record"]).drop(columns=["_sort"])
    c1, c2, c3 = st.columns(3)
    c1.metric("High", int((df["Severity"] == "High").sum()))
    c2.metric("Medium", int((df["Severity"] == "Medium").sum()))
    c3.metric("Low", int((df["Severity"] == "Low").sum()))
    areas = ["All"] + sorted(df["Area"].dropna().unique().tolist())
    selected_area = st.selectbox("Filter area", areas)
    filtered = df if selected_area == "All" else df[df["Area"] == selected_area]
    st.dataframe(filtered, hide_index=True, use_container_width=True)
    st.download_button("Download validation issues CSV", filtered.to_csv(index=False).encode("utf-8"), "kusha_validation_issues.csv", "text/csv")



def export_install_tab():
    st.subheader("Export / Install Center")
    st.info("Version 8.3 includes imported BOM recipes, live reports, validated inputs, clean Excel export and one-click launchers.")

    st.markdown("### Export current database to Excel")
    st.caption("This creates a clean report/backup workbook from the app database. It does not overwrite your original Excel file.")
    try:
        excel_bytes = engine.export_database_to_excel_v7()
        st.download_button(
            "Download clean Excel export",
            data=excel_bytes,
            file_name="kusha_costing_database_export_v8.3.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    except Exception as exc:
        st.error(f"Could not create Excel export: {exc}")

    st.markdown("### Download current SQLite database")
    try:
        db_bytes = Path(active_db).read_bytes()
        st.download_button(
            "Download current SQLite database",
            data=db_bytes,
            file_name="kusha_costing_current_v8.3.sqlite",
            mime="application/octet-stream",
        )
    except Exception as exc:
        st.error(f"Could not prepare database download: {exc}")

    st.markdown("### One-click launchers")
    notes = engine.installer_notes_v7()
    st.write("**Mac:**", notes["mac_quick_launcher"])
    st.write("**Windows:**", notes["windows_quick_launcher"])
    st.warning("A true installable .app/.exe must be built on the target operating system by a developer. This package includes launchers, not a signed production installer.")

    with st.expander("Developer packaging notes"):
        st.markdown(
            """
For internal use, keep using the included `.command` / `.bat` launchers.

For production deployment, ask your developer to choose one path:

1. **Desktop package:** PyInstaller / Briefcase / Electron wrapper.
2. **Hosted website:** FastAPI or Django backend + PostgreSQL + login system.
3. **Streamlit Cloud/internal server:** fastest hosted version, but less production-grade than a custom web stack.
"""
        )

calculator, reports, master_data, bom, transport, admin, validation, export_install, checks = st.tabs(["Calculator", "Reports", "Master Data Center", "BOM / Recipe Builder", "Transport + GST", "Admin Controls", "Validation Center", "Export / Install", "Database Check"])
with calculator:
    calculator_tab()
with reports:
    reports_tab()
with master_data:
    master_data_center_tab()
with bom:
    bom_builder_tab()
with transport:
    transport_and_gst_tab()
with admin:
    admin_controls_tab()
with validation:
    validation_center_tab()
with export_install:
    export_install_tab()
with checks:
    database_check_tab()

st.divider()
st.markdown(
    """
**Version 9.0 notes — Excel-free workflow**
- The local SQLite database is the single source of truth. Excel is now optional: use it only to seed a fresh database or as a backup/export format.
- **MRP & selling prices** are fully editable in Master Data Center → *MRP & Selling Price*, shown next to the live recalculated cost so you can price without a spreadsheet.
- **Products** can be created, edited (source, vendor, shipping, miscellaneous %, GST, category), resized (add/remove sizes) and discontinued from Admin Controls → *Manage Products*.
- Master Data Center also covers categories, item-level GST, packaging lists, packaging mapping, shipping logic, storage/labour/sticker settings, transport source costing and the BOM/recipe builder.
- The 27 masala/blend recipes stay reference-only until explicitly approved for calculator costing.
- Calculator and Reports recalculate live from the same SQLite master data; invalid/non-finite values are rejected and incomplete setups flagged.
- Database Check → *Cost reconciliation* shows exactly how app costs compare to the original workbook.
- Every edit is captured in the audit log, and the database can be backed up, restored and exported to Excel at any time.
"""
)
