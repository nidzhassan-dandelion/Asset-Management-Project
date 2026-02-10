import streamlit as st
import pandas as pd
import sqlite3

# --- 1. DATABASE CONFIGURATION ---
def get_connection():
    return sqlite3.connect('inventory_v4.db', check_same_thread=False)

def init_db():
    conn = get_connection()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS assets 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, serial TEXT, 
                  category TEXT, purchase_date TEXT, location TEXT, status TEXT, quantity INTEGER)''')
    c.execute('CREATE TABLE IF NOT EXISTS categories (name TEXT PRIMARY KEY)')
    default_cats = [("IT Equipment",), ("Office Furniture",), ("Tools",)]
    c.executemany('INSERT OR IGNORE INTO categories VALUES (?)', default_cats)
    conn.commit()

init_db()

# --- 2. AUTHENTICATION ---
st.sidebar.title("🔐 Access Control")
user_role = st.sidebar.selectbox("Current Role", ["Viewer", "Manager", "Admin"])
st.sidebar.info(f"Permissions: {user_role} Level")

# --- 3. MAIN INTERFACE ---
st.title("🛡️ Asset & Inventory System")
menu = ["Dashboard", "Manage Assets", "Category Settings", "Reports"]
choice = st.sidebar.selectbox("Navigation", menu)
conn = get_connection()

# --- FEATURE: DASHBOARD ---
if choice == "Dashboard":
    st.header("🔍 Inventory Overview")
    df = pd.read_sql('SELECT * FROM assets', conn)
    
    if not df.empty:
        # --- SMART LOGIC: Auto-update Status based on Quantity ---
        # If quantity is 0, force status to 'Out of Stock'
        df.loc[df['quantity'] == 0, 'status'] = 'Out of Stock'
        
        search = st.text_input("Search by Name or Serial")
        if search:
            df = df[df['name'].str.contains(search, case=False) | df['serial'].str.contains(search, case=False)]
        
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No assets found.")

# --- FEATURE: MANAGE ASSETS ---
elif choice == "Manage Assets":
    if user_role == "Admin":
        st.subheader("➕ Add Asset")
        with st.form("add_form", clear_on_submit=True):
            name = st.text_input("Name")
            serial = st.text_input("Serial Number")
            qty = st.number_input("Quantity", min_value=0, step=1, value=1)
            cat_list = [row[0] for row in conn.execute('SELECT name FROM categories').fetchall()]
            category = st.selectbox("Category", cat_list)
            loc = st.selectbox("Location", ["Office A", "Warehouse 1", "Remote"])
            submit = st.form_submit_button("Save")
            
            if submit:
                # Initial status: if qty is 0, it's Out of Stock, otherwise In Stock
                initial_status = "In Stock" if qty > 0 else "Out of Stock"
                conn.execute('INSERT INTO assets (name, serial, category, location, status, quantity) VALUES (?,?,?,?,?,?)',
                             (name, serial, category, loc, initial_status, qty))
                conn.commit()
                st.success("Asset Added!")

    if user_role in ["Admin", "Manager"]:
        st.divider()
        st.subheader("🔄 Update Asset")
        assets = [row[0] for row in conn.execute('SELECT name FROM assets').fetchall()]
        if assets:
            target = st.selectbox("Select Asset", assets)
            new_qty = st.number_input("Update Quantity", min_value=0, step=1)
            new_loc = st.selectbox("New Location", ["Office A", "Warehouse 1", "Remote"])
            
            if st.button("Apply Updates"):
                # Automatically determine status based on the new quantity
                updated_status = "In Stock" if new_qty > 0 else "Out of Stock"
                conn.execute('UPDATE assets SET quantity=?, location=?, status=? WHERE name=?', 
                             (new_qty, new_loc, updated_status, target))
                conn.commit()
                st.info(f"Updated! Status is now {updated_status}")

# --- FEATURE: CATEGORY & REPORTS ---
# (Same as before, simplified for space)
elif choice == "Category Settings" and user_role == "Admin":
    new_cat = st.text_input("New Category")
    if st.button("Add"):
        conn.execute('INSERT OR IGNORE INTO categories VALUES (?)', (new_cat,))
        conn.commit()
        st.rerun()

elif choice == "Reports":
    df_all = pd.read_sql('SELECT * FROM assets', conn)
    # Ensure status is accurate in reports too
    df_all.loc[df_all['quantity'] == 0, 'status'] = 'Out of Stock'
    st.table(df_all[df_all['quantity'] <= 5]) # Low Stock Report
