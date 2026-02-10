import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime

# --- 1. DATABASE CONFIGURATION ---
def get_connection():
    # Using v3 to ensure the status changes take effect on a clean slate
    conn = sqlite3.connect('inventory_v3.db', check_same_thread=False)
    return conn

def init_db():
    conn = get_connection()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS assets 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  name TEXT, 
                  serial TEXT, 
                  category TEXT, 
                  purchase_date TEXT, 
                  location TEXT, 
                  status TEXT, 
                  quantity INTEGER)''')
    c.execute('CREATE TABLE IF NOT EXISTS categories (name TEXT PRIMARY KEY)')
    default_cats = [("IT Equipment",), ("Office Furniture",), ("Tools",)]
    c.executemany('INSERT OR IGNORE INTO categories VALUES (?)', default_cats)
    conn.commit()

init_db()

# --- 2. AUTHENTICATION SIDEBAR ---
st.sidebar.title("🔐 System Access")
user_role = st.sidebar.selectbox("Select Your Role", ["Viewer", "Manager", "Admin"])
st.sidebar.divider()

# --- 3. MAIN INTERFACE ---
st.title("🛡️ Asset & Inventory System")
menu = ["Dashboard & Search", "Manage Assets", "Category Settings", "Reports"]
choice = st.sidebar.selectbox("Navigation", menu)

conn = get_connection()

# --- FEATURE: DASHBOARD & SEARCH ---
if choice == "Dashboard & Search":
    st.header("🔍 Search & Filter Inventory")
    df = pd.read_sql('SELECT * FROM assets', conn)
    
    if not df.empty:
        search_query = st.text_input("Search by Name or Serial Number")
        if search_query:
            df = df[df['name'].str.contains(search_query, case=False) | 
                    df['serial'].str.contains(search_query, case=False)]
        
        col1, col2 = st.columns(2)
        with col1:
            loc_filter = st.multiselect("Filter by Location", df['location'].unique())
        with col2:
            # ONLY 2 OPTIONS HERE
            stat_filter = st.multiselect("Filter by Status", ["In Stock", "Out of Stock"])
        
        if loc_filter:
            df = df[df['location'].isin(loc_filter)]
        if stat_filter:
            df = df[df['status'].isin(stat_filter)]
            
        st.dataframe(df, use_container_width=True)
    else:
        st.info("The inventory is empty. Switch to Admin to add assets.")

# --- FEATURE: MANAGE ASSETS (CRUD) ---
elif choice == "Manage Assets":
    if user_role == "Admin":
        st.subheader("➕ Add New Asset")
        with st.form("add_form", clear_on_submit=True):
            col_a, col_b = st.columns(2)
            with col_a:
                name = st.text_input("Asset Name")
                serial = st.text_input("Serial Number")
                cat_query = conn.execute('SELECT name FROM categories').fetchall()
                cat_list = [row[0] for row in cat_query]
                category = st.selectbox("Category", cat_list)
            with col_b:
                p_date = st.date_input("Purchase Date")
                loc = st.selectbox("Initial Location", ["Office A", "Warehouse 1", "Remote"])
                qty = st.number_input("Total Quantity", min_value=1, step=1, value=1)
            
            submit = st.form_submit_button("Save Asset")
            
            if submit:
                # DEFAULT STATUS SET TO 'In Stock'
                conn.execute('''INSERT INTO assets 
                             (name, serial, category, purchase_date, location, status, quantity) 
                             VALUES (?,?,?,?,?,?,?)''',
                             (name, serial, category, str(p_date), loc, "In Stock", qty))
                conn.commit()
                st.success(f"Asset '{name}' added successfully!")

    if user_role in ["Admin", "Manager"]:
        st.divider()
        st.subheader("🔄 Update Asset Status/Location")
        asset_names = [row[0] for row in conn.execute('SELECT name FROM assets').fetchall()]
        
        if asset_names:
            asset_to_update = st.selectbox("Select Asset to Update", asset_names)
            c1, c2 = st.columns(2)
            with c1:
                new_loc = st.selectbox("Update Location", ["Office A", "Warehouse 1", "Remote"])
            with c2:
                # ONLY 2 OPTIONS HERE
                new_stat = st.selectbox("Update Status", ["In Stock", "Out of Stock"])
            
            if st.button("Update Asset Details"):
                conn.execute('UPDATE assets SET location=?, status=? WHERE name=?', (new_loc, new_stat, asset_to_update))
                conn.commit()
                st.info("Asset status updated!")
        else:
            st.warning("No assets available to update.")

    if user_role == "Admin":
        st.divider()
        st.subheader("🗑️ Delete Asset")
        asset_names = [row[0] for row in conn.execute('SELECT name FROM assets').fetchall()]
        if asset_names:
            asset_to_del = st.selectbox("Select Asset to Permanently Remove", asset_names)
            if st.button("CONFIRM DELETE"):
                conn.execute('DELETE FROM assets WHERE name=?', (asset_to_del,))
                conn.commit()
                st.warning("Asset removed.")

# --- FEATURE: CATEGORY MANAGEMENT ---
elif choice == "Category Settings":
    if user_role == "Admin":
        st.header("Manage Categories")
        new_cat = st.text_input("New Category Name")
        if st.button("Add Category"):
            if new_cat:
                try:
                    conn.execute('INSERT INTO categories VALUES (?)', (new_cat,))
                    conn.commit()
                    st.success("Category added!")
                    st.rerun()
                except:
                    st.error("Already exists.")
    else:
        st.error("Admin only.")

# --- FEATURE: REPORTS ---
elif choice == "Reports":
    st.header("📊 System Reports")
    rep_type = st.radio("Select Report Type", ["Assets by Location", "Low Stock Alert (< 5 units)"])
    df_all = pd.read_sql('SELECT * FROM assets', conn)
    
    if rep_type == "Assets by Location":
        target_loc = st.selectbox("Select Location", ["Office A", "Warehouse 1", "Remote"])
        report_df = df_all[df_all['location'] == target_loc]
    else:
        report_df = df_all[df_all['quantity'] <= 5]
        
    st.dataframe(report_df, use_container_width=True)
    if not report_df.empty:
        csv = report_df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Export CSV", data=csv, file_name="report.csv")
