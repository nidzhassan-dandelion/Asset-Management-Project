import streamlit as st
import pandas as pd
import sqlite3

# --- 1. DATABASE CONFIGURATION ---
def get_connection():
    # v10 for a completely clean start without forced defaults
    return sqlite3.connect('inventory_final_v10.db', check_same_thread=False)

def init_db():
    conn = get_connection()
    c = conn.cursor()
    # Create Assets Table
    c.execute('''CREATE TABLE IF NOT EXISTS assets 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, serial TEXT, 
                  category TEXT, purchase_date TEXT, location TEXT, status TEXT, quantity INTEGER)''')
    # Create Categories Table (No defaults inserted)
    c.execute('CREATE TABLE IF NOT EXISTS categories (name TEXT PRIMARY KEY)')
    # Create Locations Table (No defaults inserted)
    c.execute('CREATE TABLE IF NOT EXISTS locations (name TEXT PRIMARY KEY)')
    conn.commit()

init_db()

# --- 2. AUTHENTICATION SIDEBAR ---
st.sidebar.title("🔐 Access Control")
user_role = st.sidebar.selectbox("Current Role", ["Viewer", "Manager", "Admin"])
st.sidebar.divider()

# --- 3. MAIN INTERFACE ---
st.title("🛡️ Asset & Inventory System")
menu = ["Dashboard", "Manage Assets", "Category Settings", "Initial Location Settings", "Reports"]
choice = st.sidebar.selectbox("Navigation", menu)
conn = get_connection()

# --- DASHBOARD ---
if choice == "Dashboard":
    st.header("🔍 Inventory Overview")
    df = pd.read_sql('SELECT * FROM assets', conn)
    if not df.empty:
        df.loc[df['quantity'] == 0, 'status'] = 'Out of Stock'
        df.loc[df['quantity'] > 0, 'status'] = 'In Stock'
        search = st.text_input("Search by Name, Serial, or Category")
        if search:
            df = df[df['name'].str.contains(search, case=False) | df['serial'].str.contains(search, case=False) | df['category'].str.contains(search, case=False)]
        st.dataframe(df, use_container_width=True)
    else:
        st.info("Inventory is empty.")

# --- MANAGE ASSETS ---
elif choice == "Manage Assets":
    if user_role == "Admin":
        st.subheader("➕ Add New Asset")
        cat_list = [row[0] for row in conn.execute('SELECT name FROM categories').fetchall()]
        loc_list = [row[0] for row in conn.execute('SELECT name FROM locations').fetchall()]
        
        if not cat_list or not loc_list:
            st.warning("Please add at least one Category and one Location in the settings tabs before adding assets.")
        else:
            with st.form("add_form", clear_on_submit=True):
                col1, col2 = st.columns(2)
                with col1:
                    name = st.text_input("Asset Name")
                    serial = st.text_input("Serial Number")
                    category = st.selectbox("Category", cat_list)
                with col2:
                    qty = st.number_input("Quantity", min_value=0, step=1, value=1)
                    loc = st.selectbox("Location", loc_list)
                    p_date = st.date_input("Purchase Date")
                if st.form_submit_button("Save Asset"):
                    status = "In Stock" if qty > 0 else "Out of Stock"
                    conn.execute('INSERT INTO assets (name, serial, category, purchase_date, location, status, quantity) VALUES (?,?,?,?,?,?,?)', (name, serial, category, str(p_date), loc, status, qty))
                    conn.commit()
                    st.success(f"Added {name}")

    if user_role in ["Admin", "Manager"]:
        st.divider()
        st.subheader("🔄 Update Status/Location")
        asset_query = pd.read_sql('SELECT * FROM assets', conn)
        if not asset_query.empty:
            target = st.selectbox("Select Asset to Update", asset_query['name'].tolist())
            current_row = asset_query[asset_query['name'] == target].iloc[0]
            curr_qty, curr_loc = int(current_row['quantity']), current_row['location']
            st.info(f"**Current:** Qty: {curr_qty} | Loc: {curr_loc}")
            u1, u2 = st.columns(2)
            with u1: new_qty = st.number_input("New Quantity", min_value=0, step=1, value=curr_qty)
            with u2:
                loc_options = [row[0] for row in conn.execute('SELECT name FROM locations').fetchall()]
                curr_idx = loc_options.index(curr_loc) if curr_loc in loc_options else 0
                new_loc = st.selectbox("New Location", loc_options, index=curr_idx)
            if st.button("Apply Changes"):
                new_status = "In Stock" if new_qty > 0 else "Out of Stock"
                conn.execute('UPDATE assets SET quantity=?, location=?, status=? WHERE name=?', (new_qty, new_loc, new_status, target))
                conn.commit()
                st.success("Updated!"); st.rerun()

    if user_role == "Admin":
        st.divider()
        st.subheader("🗑️ Delete Asset")
        assets_del = [row[0] for row in conn.execute('SELECT name FROM assets').fetchall()]
        if assets_del:
            target_del = st.selectbox("Select Asset to Delete", assets_del)
            if st.button("Confirm Delete Asset"):
                conn.execute('DELETE FROM assets WHERE name=?', (target_del,))
                conn.commit(); st.rerun()

# --- CATEGORY SETTINGS ---
elif choice == "Category Settings":
    if user_role == "Admin":
        st.subheader("📂 Manage Categories")
        with st.expander("➕ Add New Category"):
            new_cat = st.text_input("New Name")
            if st.button("Save New Category"):
                if new_cat: 
                    conn.execute('INSERT OR IGNORE INTO categories VALUES (?)', (new_cat,))
                    conn.commit(); st.rerun()
        with st.expander("📝 Edit Category Name"):
            cat_list = [row[0] for row in conn.execute('SELECT name FROM categories').fetchall()]
            if cat_list:
                old_name = st.selectbox("Select Category to Rename", cat_list)
                renamed = st.text_input("New Name for selected category")
                if st.button("Update Category Name"):
                    if renamed: 
                        conn.execute('UPDATE categories SET name=? WHERE name=?', (renamed, old_name))
                        conn.commit(); st.rerun()
        with st.expander("🗑️ Delete Category"):
            cat_list_del = [row[0] for row in conn.execute('SELECT name FROM categories').fetchall()]
            if cat_list_del:
                cat_to_del = st.selectbox("Select Category to Remove", cat_list_del)
                if st.button("Permanently Delete Category"):
                    conn.execute('DELETE FROM categories WHERE name=?', (cat_to_del,))
                    conn.commit(); st.rerun()
        st.divider(); st.write("Current List:"); st.table(pd.read_sql('SELECT * FROM categories', conn))
    else: st.error("Admin Only")

# --- LOCATION SETTINGS ---
elif choice == "Initial Location Settings":
    if user_role == "Admin":
        st.subheader("📍 Manage Locations")
        with st.expander("➕ Add New Location"):
            new_l = st.text_input("New Location Name")
            if st.button("Save New Location"):
                if new_l: 
                    conn.execute('INSERT OR IGNORE INTO locations VALUES (?)', (new_l,))
                    conn.commit(); st.rerun()
        with st.expander("📝 Edit Location Name"):
            loc_list = [row[0] for row in conn.execute('SELECT name FROM locations').fetchall()]
            if loc_list:
                old_l = st.selectbox("Select Location to Rename", loc_list)
                ren_l = st.text_input("New Name for selected location")
                if st.button("Update Location Name"):
                    if ren_l: 
                        conn.execute('UPDATE locations SET name=? WHERE name=?', (ren_l, old_l))
                        conn.commit(); st.rerun()
        with st.expander("🗑️ Delete Location"):
            loc_list_del = [row[0] for row in conn.execute('SELECT name FROM locations').fetchall()]
            if loc_list_del:
                l_to_del = st.selectbox("Select Location to Remove", loc_list_del)
                if st.button("Permanently Delete Location"):
                    conn.execute('DELETE FROM locations WHERE name=?', (l_to_del,))
                    conn.commit(); st.rerun()
        st.divider(); st.write("Current List:"); st.table(pd.read_sql('SELECT * FROM locations', conn))
    else: st.error("Admin Only")

# --- REPORTS ---
elif choice == "Reports":
    st.header("📊 Exportable Reports")
    rep_type = st.radio("Choose Report", ["Assets by Location", "Low Stock Alert (<= 5 units)"])
    df_rep = pd.read_sql('SELECT * FROM assets', conn)
    if not df_rep.empty:
        df_rep.loc[df_rep['quantity'] == 0, 'status'] = 'Out of Stock'
        df_rep.loc[df_rep['quantity'] > 0, 'status'] = 'In Stock'
        if rep_type == "Assets by Location":
            l_opts = [row[0] for row in conn.execute('SELECT name FROM locations').fetchall()]
            if l_opts:
                l_choice = st.selectbox("Select Location", l_opts)
                final_df = df_rep[df_rep['location'] == l_choice]
                st.dataframe(final_df, use_container_width=True)
                csv_data = final_df.to_csv(index=False).encode('utf-8')
                st.download_button("📥 Download CSV", csv_data, "report.csv", "text/csv")
            else: st.warning("No locations defined.")
        else: 
            final_df = df_rep[df_rep['quantity'] <= 5]
            st.dataframe(final_df, use_container_width=True)
            csv_data = final_df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download CSV", csv_data, "report.csv", "text/csv")
    else: st.info("No data available.")
