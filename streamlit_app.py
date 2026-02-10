import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime

# --- 1. DATABASE CONFIGURATION ---
def get_connection():
    conn = sqlite3.connect('inventory.db', check_same_thread=False)
    return conn

def init_db():
    conn = get_connection()
    c = conn.cursor()
    # Assets Table
    c.execute('''CREATE TABLE IF NOT EXISTS assets 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, serial TEXT, 
                  category TEXT, purchase_date TEXT, location TEXT, status TEXT)''')
    # Categories Table
    c.execute('CREATE TABLE IF NOT EXISTS categories (name TEXT PRIMARY KEY)')
    # Default Categories
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

# --- FEATURE: DASHBOARD & SEARCH (All Roles) ---
if choice == "Dashboard & Search":
    st.header("Search Inventory")
    search_query = st.text_input("🔍 Search by Name or Serial Number")
    
    df = pd.read_sql('SELECT * FROM assets', conn)
    
    if search_query:
        df = df[df['name'].str.contains(search_query, case=False) | 
                df['serial'].str.contains(search_query, case=False)]
    
    # Filtering
    col1, col2 = st.columns(2)
    with col1:
        loc_filter = st.multiselect("Filter by Location", df['location'].unique())
    with col2:
        stat_filter = st.multiselect("Filter by Status", df['status'].unique())
    
    if loc_filter:
        df = df[df['location'].isin(loc_filter)]
    if stat_filter:
        df = df[df['status'].isin(stat_filter)]
        
    st.dataframe(df, use_container_width=True)

# --- FEATURE: MANAGE ASSETS (CRUD) ---
elif choice == "Manage Assets":
    if user_role == "Admin":
        st.subheader("➕ Add New Asset")
        with st.form("add_form", clear_on_submit=True):
            name = st.text_input("Asset Name")
            serial = st.text_input("Serial Number")
            cat_list = [row[0] for row in conn.execute('SELECT name FROM categories').fetchall()]
            category = st.selectbox("Category", cat_list)
            p_date = st.date_input("Purchase Date")
            loc = st.selectbox("Initial Location", ["Office A", "Warehouse 1", "Remote"])
            submit = st.form_submit_button("Save Asset")
            
            if submit:
                conn.execute('INSERT INTO assets (name, serial, category, purchase_date, location, status) VALUES (?,?,?,?,?,?)',
                             (name, serial, category, str(p_date), loc, "In Stock"))
                conn.commit()
                st.success(f"Asset '{name}' added successfully!")

    if user_role in ["Admin", "Manager"]:
        st.subheader("Edit/Update Asset")
        asset_to_update = st.selectbox("Select Asset to Update", pd.read_sql('SELECT name FROM assets', conn))
        new_loc = st.selectbox("Update Location", ["Office A", "Warehouse 1", "Remote", "In Repair"])
        new_stat = st.selectbox("Update Status", ["In Use", "In Repair", "In Stock", "Available"])
        
        if st.button("Update Asset"):
            conn.execute('UPDATE assets SET location=?, status=? WHERE name=?', (new_loc, new_stat, asset_to_update))
            conn.commit()
            st.info("Status updated!")

    if user_role == "Admin":
        st.divider()
        st.subheader("🗑️ Delete Asset")
        asset_to_del = st.selectbox("Select Asset to Permanently Remove", pd.read_sql('SELECT name FROM assets', conn))
        if st.button("CONFIRM DELETE"):
            conn.execute('DELETE FROM assets WHERE name=?', (asset_to_del,))
            conn.commit()
            st.warning("Asset Deleted.")

# --- FEATURE: CATEGORY MANAGEMENT (Admin Only) ---
elif choice == "Category Settings":
    if user_role == "Admin":
        st.header("Category Management")
        new_cat = st.text_input("Add New Category Name")
        if st.button("Add Category"):
            try:
                conn.execute('INSERT INTO categories VALUES (?)', (new_cat,))
                conn.commit()
                st.success("Category Added!")
            except:
                st.error("Category already exists.")
    else:
        st.error("Access Denied: Admin only.")

# --- FEATURE: REPORTS ---
elif choice == "Reports":
    st.header("System Reports")
    rep_type = st.radio("Select Report Type", ["Assets by Location", "Low Stock Alert (IT)"])
    
    if rep_type == "Assets by Location":
        target_loc = st.selectbox("Select Location", ["Office A", "Warehouse 1", "Remote"])
        report_df = pd.read_sql('SELECT * FROM assets WHERE location=?', conn, params=(target_loc,))
    else:
        # Low Stock Simulation: Shows categories with less than 5 items
        report_df = pd.read_sql('SELECT category, COUNT(*) as Quantity FROM assets GROUP BY category HAVING Quantity < 5', conn)
        st.warning("The following categories have low inventory (< 5 items):")
        
    st.table(report_df)
    
    # Export Button
    csv = report_df.to_csv(index=False).encode('utf-8')
    st.download_button("📥 Export Report to CSV", data=csv, file_name="asset_report.csv", mime="text/csv")
