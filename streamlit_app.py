import streamlit as st
import pandas as pd
import sqlite3

# --- 1. DATABASE CONFIGURATION ---
def get_connection():
    # v7 ensures a clean start with all integrated logic
    return sqlite3.connect('inventory_final.db', check_same_thread=False)

def init_db():
    conn = get_connection()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS assets 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, serial TEXT, 
                  category TEXT, purchase_date TEXT, location TEXT, status TEXT, quantity INTEGER)''')
    c.execute('CREATE TABLE IF NOT EXISTS categories (name TEXT PRIMARY KEY)')
    # Default categories required by the brief
    default_cats = [("IT Equipment",), ("Office Furniture",), ("Tools",)]
    c.executemany('INSERT OR IGNORE INTO categories VALUES (?)', default_cats)
    conn.commit()

init_db()

# --- 2. AUTHENTICATION SIDEBAR ---
st.sidebar.title("🔐 Access Control")
user_role = st.sidebar.selectbox("Current Role", ["Viewer", "Manager", "Admin"])
st.sidebar.divider()

# --- 3. MAIN INTERFACE ---
st.title("🛡️ Asset & Inventory System")
menu = ["Dashboard", "Manage Assets", "Category Settings", "Reports"]
choice = st.sidebar.selectbox("Navigation", menu)
conn = get_connection()

# --- FEATURE: DASHBOARD (SEARCH & VIEW) ---
if choice == "Dashboard":
    st.header("🔍 Inventory Overview")
    df = pd.read_sql('SELECT * FROM assets', conn)
    if not df.empty:
        # AUTOMATIC STATUS LOGIC
        df.loc[df['quantity'] == 0, 'status'] = 'Out of Stock'
        df.loc[df['quantity'] > 0, 'status'] = 'In Stock'
        
        search = st.text_input("Search by Name, Serial, or Category")
        if search:
            df = df[df['name'].str.contains(search, case=False) | 
                    df['serial'].str.contains(search, case=False) |
                    df['category'].str.contains(search, case=False)]
        st.dataframe(df, use_container_width=True)
    else:
        st.info("Inventory is currently empty. Use Admin role to add assets.")

# --- FEATURE: MANAGE ASSETS (CRUD + PRE-FILL LOGIC) ---
elif choice == "Manage Assets":
    if user_role == "Admin":
        st.subheader("➕ Add New Asset")
        with st.form("add_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                name = st.text_input("Asset Name")
                serial = st.text_input("Serial Number")
                cat_list = [row[0] for row in conn.execute('SELECT name FROM categories').fetchall()]
                category = st.selectbox("Category", cat_list)
            with col2:
                qty = st.number_input("Quantity", min_value=0, step=1, value=1)
                loc = st.selectbox("Initial Location", ["Office A", "Warehouse 1", "Remote Employee"])
                p_date = st.date_input("Purchase Date")
            
            if st.form_submit_button("Save Asset"):
                # Initial Auto-status
                status = "In Stock" if qty > 0 else "Out of Stock"
                conn.execute('INSERT INTO assets (name, serial, category, purchase_date, location, status, quantity) VALUES (?,?,?,?,?,?,?)',
                             (name, serial, category, str(p_date), loc, status, qty))
                conn.commit()
                st.success(f"Successfully added {name}")

    if user_role in ["Admin", "Manager"]:
        st.divider()
        st.subheader("🔄 Update Status/Location (Pre-filled)")
        asset_query = pd.read_sql('SELECT * FROM assets', conn)
        
        if not asset_query.empty:
            asset_names = asset_query['name'].tolist()
            target = st.selectbox("Select Asset to Update", asset_names)
            
            # PRE-FILL LOGIC: Fetch current values
            current_row = asset_query[asset_query['name'] == target].iloc[0]
            curr_qty = int(current_row['quantity'])
            curr_loc = current_row['location']
            
            st.info(f"**Current Data:** Quantity: {curr_qty} | Location: {curr_loc}")
            
            col_u1, col_u2 = st.columns(2)
            with col_u1:
                new_qty = st.number_input("Update Quantity", min_value=0, step=1, value=curr_qty)
            with col_u2:
                loc_options = ["Office A", "Warehouse 1", "Remote Employee"]
                curr_idx = loc_options.index(curr_loc) if curr_loc in loc_options else 0
                new_loc = st.selectbox("Update Location", loc_options, index=curr_idx)
            
            if st.button("Apply Changes"):
                # Force Auto-status based on new quantity
                new_status = "In Stock" if new_qty > 0 else "Out of Stock"
                conn.execute('UPDATE assets SET quantity=?, location=?, status=? WHERE name=?', 
                             (new_qty, new_loc, new_status, target))
                conn.commit()
                st.success("Asset updated!")
                st.rerun()
        else:
            st.warning("No assets to update.")

    if user_role == "Admin":
        st.divider()
        st.subheader("🗑️ Delete Asset")
        assets_del = [row[0] for row in conn.execute('SELECT name FROM assets').fetchall()]
        if assets_del:
            target_del = st.selectbox("Select Asset to Delete", assets_del)
            if st.button("Confirm Permanent Delete"):
                conn.execute('DELETE FROM assets WHERE name=?', (target_del,))
                conn.commit()
                st.rerun()

# --- FEATURE: CATEGORY MANAGEMENT ---
elif choice == "Category Settings":
    if user_role == "Admin":
        st.subheader("📂 Manage Categories")
        new_cat = st.text_input("Enter New Category Name")
        if st.button("Add Category"):
            if new_cat:
                conn.execute('INSERT OR IGNORE INTO categories (name) VALUES (?)', (new_cat,))
                conn.commit()
                st.rerun()
    else:
        st.error("Access Denied: Admin role required.")

# --- FEATURE: REPORTS (PRINTABLE/EXPORTABLE) ---
elif choice == "Reports":
    st.header("📊 Exportable Reports")
    report_type = st.radio("Choose Report", ["Assets by Location", "Low Stock Alert (<= 5 units)"])
    
    df_rep = pd.read_sql('SELECT * FROM assets', conn)
    if not df_rep.empty:
        # Ensure status is accurate in the report view
        df_rep.loc[df_rep['quantity'] == 0, 'status'] = 'Out of Stock'
        df_rep.loc[df_rep['quantity'] > 0, 'status'] = 'In Stock'

        if report_type == "Assets by Location":
            loc_choice = st.selectbox("Select Location for Report", ["Office A", "Warehouse 1", "Remote Employee"])
            final_df = df_rep[df_rep['location'] == loc_choice]
            st.subheader(f"Assets in {loc_choice}")
        else:
            final_df = df_rep[df_rep['quantity'] <= 5]
            st.subheader("Low Stock Inventory")

        st.dataframe(final_df, use_container_width=True)
        
        # EXPORT BUTTON
        csv_data = final_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download Report (CSV)",
            data=csv_data,
            file_name=f"{report_type.lower().replace(' ', '_')}.csv",
            mime="text/csv"
        )
    else:
        st.info("No data available for reports.")
