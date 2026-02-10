import streamlit as st
import pandas as pd
import sqlite3

# --- 1. DATABASE CONFIGURATION ---
def get_connection():
    # v5 to ensure all new logic is fresh
    return sqlite3.connect('inventory_v5.db', check_same_thread=False)

def init_db():
    conn = get_connection()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS assets 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, serial TEXT, 
                  category TEXT, purchase_date TEXT, location TEXT, status TEXT, quantity INTEGER)''')
    c.execute('CREATE TABLE IF NOT EXISTS categories (name TEXT PRIMARY KEY)')
    # Adding default categories
    default_cats = [("IT Equipment",), ("Office Furniture",), ("Tools",)]
    c.executemany('INSERT OR IGNORE INTO categories VALUES (?)', default_cats)
    conn.commit()

init_db()

# --- 2. AUTHENTICATION SIDEBAR ---
st.sidebar.title("🔐 Access Control")
user_role = st.sidebar.selectbox("Current Role", ["Viewer", "Manager", "Admin"])

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
        # AUTOMATIC LOGIC: If quantity is 0, status is Out of Stock
        df.loc[df['quantity'] == 0, 'status'] = 'Out of Stock'
        df.loc[df['quantity'] > 0, 'status'] = 'In Stock'
        
        search = st.text_input("Search by Name, Serial, or Category")
        if search:
            df = df[df['name'].str.contains(search, case=False) | 
                    df['serial'].str.contains(search, case=False) |
                    df['category'].str.contains(search, case=False)]
        st.dataframe(df, use_container_width=True)
    else:
        st.info("Inventory is empty.")

# --- FEATURE: MANAGE ASSETS (CRUD) ---
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
                loc = st.selectbox("Location", ["Office A", "Warehouse 1", "Remote Employee"])
                p_date = st.date_input("Purchase Date")
            
            if st.form_submit_button("Save Asset"):
                # Status Logic
                status = "In Stock" if qty > 0 else "Out of Stock"
                conn.execute('INSERT INTO assets (name, serial, category, purchase_date, location, status, quantity) VALUES (?,?,?,?,?,?,?)',
                             (name, serial, category, str(p_date), loc, status, qty))
                conn.commit()
                st.success("Asset Added!")

    if user_role in ["Admin", "Manager"]:
        st.divider()
        st.subheader("🔄 Update Status/Location")
        assets = [row[0] for row in conn.execute('SELECT name FROM assets').fetchall()]
        if assets:
            target = st.selectbox("Select Asset to Update", assets)
            new_qty = st.number_input("Update Quantity", min_value=0, step=1)
            new_loc = st.selectbox("New Location", ["Office A", "Warehouse 1", "Remote Employee"])
            
            if st.button("Update Asset"):
                status = "In Stock" if new_qty > 0 else "Out of Stock"
                conn.execute('UPDATE assets SET quantity=?, location=?, status=? WHERE name=?', 
                             (new_qty, new_loc, status, target))
                conn.commit()
                st.rerun()

    if user_role == "Admin":
        st.divider()
        st.subheader("🗑️ Delete Asset")
        assets_del = [row[0] for row in conn.execute('SELECT name FROM assets').fetchall()]
        if assets_del:
            target_del = st.selectbox("Remove Asset", assets_del)
            if st.button("Confirm Delete"):
                conn.execute('DELETE FROM assets WHERE name=?', (target_del,))
                conn.commit()
                st.rerun()

# --- FEATURE: CATEGORY MANAGEMENT ---
elif choice == "Category Settings":
    if user_role == "Admin":
        st.subheader("📂 Manage Categories")
        new_cat = st.text_input("New Category Name")
        if st.button("Add"):
            conn.execute('INSERT OR IGNORE INTO categories VALUES (?)', (new_cat,))
            conn.commit()
            st.rerun()
    else:
        st.error("Admin Only")

# --- FEATURE: REPORTS (THE 2 MAJOR POINTS) ---
elif choice == "Reports":
    st.header("📋 Exportable Reports")
    report_type = st.radio("Select Report Type", ["Assets by Location", "Low Stock Alert"])
    
    df_all = pd.read_sql('SELECT * FROM assets', conn)
    # Applying the auto-status logic to the report data
    df_all.loc[df_all['quantity'] == 0, 'status'] = 'Out of Stock'
    df_all.loc[df_all['quantity'] > 0, 'status'] = 'In Stock'

    if report_type == "Assets by Location":
        loc_choice = st.selectbox("Select Location", ["Office A", "Warehouse 1", "Remote Employee"])
        final_report = df_all[df_all['location'] == loc_choice]
        st.subheader(f"Assets currently in: {loc_choice}")
    
    else: # Low Stock Alert
        threshold = 5
        final_report = df_all[df_all['quantity'] < threshold]
        st.subheader(f"Items with Quantity Less Than {threshold}")
        st.warning("Attention: These items require restocking.")

    st.dataframe(final_report, use_container_width=True)
    
    # EXPORT BUTTON
    if not final_report.empty:
        csv = final_report.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download Report as CSV",
            data=csv,
            file_name=f"{report_type.replace(' ', '_')}.csv",
            mime="text/csv",
        )
