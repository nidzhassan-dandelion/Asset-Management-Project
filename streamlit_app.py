import streamlit as st
import pandas as pd
import sqlite3
import hashlib

# --- 1. DATABASE & SECURITY CONFIG ---
def get_connection():
    return sqlite3.connect('inventory_final_v14.db', check_same_thread=False)

def make_hashes(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def check_hashes(password, hashed_text):
    if make_hashes(password) == hashed_text:
        return hashed_text
    return False

def init_db():
    conn = get_connection()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS assets 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, serial TEXT, 
                  category TEXT, purchase_date TEXT, location TEXT, status TEXT, quantity INTEGER)''')
    c.execute('CREATE TABLE IF NOT EXISTS categories (name TEXT PRIMARY KEY)')
    c.execute('CREATE TABLE IF NOT EXISTS locations (name TEXT PRIMARY KEY)')
    c.execute('CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT, role TEXT)')
    
    admin_hash = make_hashes('password123')
    c.execute('INSERT OR IGNORE INTO users (username, password, role) VALUES (?,?,?)', ('admin', admin_hash, 'Admin'))
    conn.commit()

init_db()

# --- 2. LOGIN SESSION STATE ---
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
    st.session_state['role'] = None
    st.session_state['username'] = None

# --- 3. LOGIN SIDEBAR UI ---
st.sidebar.title("🔐 Secure Login")
if not st.session_state['logged_in']:
    username = st.sidebar.text_input("Username")
    password = st.sidebar.text_input("Password", type='password')
    if st.sidebar.button("Login"):
        conn = get_connection()
        c = conn.cursor()
        c.execute('SELECT * FROM users WHERE username = ?', (username,))
        user_data = c.fetchone()
        if user_data and check_hashes(password, user_data[1]):
            st.session_state['logged_in'] = True
            st.session_state['role'] = user_data[2]
            st.session_state['username'] = username
            st.rerun()
        else:
            st.sidebar.error("Invalid Username/Password")
else:
    st.sidebar.write(f"Logged in as: **{st.session_state['username']}**")
    st.sidebar.write(f"Role: **{st.session_state['role']}**")
    if st.sidebar.button("Logout"):
        st.session_state['logged_in'] = False
        st.session_state['role'] = None
        st.rerun()

# --- 4. MAIN APP CONTENT ---
if st.session_state['logged_in']:
    user_role = st.session_state['role']
    st.title("🛡️ Asset & Inventory System")
    
    menu = ["Dashboard", "Manage Assets", "Category Settings", "Initial Location Settings", "Reports"]
    if user_role == "Admin":
        menu.append("User Management")
        
    choice = st.sidebar.selectbox("Navigation", menu)
    conn = get_connection()

    # --- DASHBOARD (SEARCH & FILTERING) ---
    if choice == "Dashboard":
        st.header("🔍 Inventory Overview")
        df = pd.read_sql('SELECT * FROM assets', conn)
        if not df.empty:
            df.loc[df['quantity'] == 0, 'status'] = 'Out of Stock'
            df.loc[df['quantity'] > 0, 'status'] = 'In Stock'
            
            col_s1, col_s2, col_s3 = st.columns(3)
            with col_s1:
                search = st.text_input("Search (Name/Serial/Category)")
            with col_s2:
                status_filter = st.multiselect("Filter by Status", ["In Stock", "Out of Stock"])
            with col_s3:
                loc_list_db = [r[0] for r in conn.execute('SELECT name FROM locations').fetchall()]
                loc_filter = st.multiselect("Filter by Location", loc_list_db)

            if search:
                df = df[df['name'].str.contains(search, case=False) | df['serial'].str.contains(search, case=False) | df['category'].str.contains(search, case=False)]
            if status_filter:
                df = df[df['status'].isin(status_filter)]
            if loc_filter:
                df = df[df['location'].isin(loc_filter)]
            st.dataframe(df, use_container_width=True)
        else:
            st.info("Inventory is empty.")

    # --- MANAGE ASSETS ---
    elif choice == "Manage Assets":
        if user_role == "Admin":
            st.subheader("➕ Add New Asset")
            st.caption("⚠️ Only Admin is authorized to add new assets.")
            cat_list = [row[0] for row in conn.execute('SELECT name FROM categories').fetchall()]
            loc_list = [row[0] for row in conn.execute('SELECT name FROM locations').fetchall()]
            if not cat_list or not loc_list:
                st.warning("Please add Categories and Locations first!")
            else:
                with st.form("add_form", clear_on_submit=True):
                    col1, col2 = st.columns(2)
                    with col1:
                        name, serial = st.text_input("Asset Name"), st.text_input("Serial Number")
                        category = st.selectbox("Category", cat_list)
                    with col2:
                        qty = st.number_input("Quantity", min_value=0, value=1)
                        loc = st.selectbox("Location", loc_list)
                        p_date = st.date_input("Purchase Date")
                    if st.form_submit_button("Save Asset"):
                        status = "In Stock" if qty > 0 else "Out of Stock"
                        conn.execute('INSERT INTO assets (name, serial, category, purchase_date, location, status, quantity) VALUES (?,?,?,?,?,?,?)', (name, serial, category, str(p_date), loc, status, qty))
                        conn.commit(); st.success(f"Added {name}")

        if user_role in ["Admin", "Manager"]:
            st.divider(); st.subheader("🔄 Update Status/Location")
            st.caption("⚠️ Only Admin and Manager are authorized to update assets.")
            asset_query = pd.read_sql('SELECT * FROM assets', conn)
            if not asset_query.empty:
                target = st.selectbox("Select Asset to Update", asset_query['name'].tolist(), key="asset_update_list")
                row = asset_query[asset_query['name'] == target].iloc[0]
                st.info(f"**Current:** Qty: {int(row['quantity'])} | Loc: {row['location']}")
                u1, u2 = st.columns(2)
                with u1: new_qty = st.number_input("New Quantity", min_value=0, value=int(row['quantity']))
                with u2: 
                    l_opts = [r[0] for r in conn.execute('SELECT name FROM locations').fetchall()]
                    curr_idx = l_opts.index(row['location']) if row['location'] in l_opts else 0
                    new_loc = st.selectbox("New Location", l_opts, index=curr_idx)
                if st.button("Apply Changes"):
                    new_status = "In Stock" if new_qty > 0 else "Out of Stock"
                    conn.execute('UPDATE assets SET quantity=?, location=?, status=? WHERE name=?', (new_qty, new_loc, new_status, target))
                    conn.commit(); st.success("Updated!"); st.rerun()

    # --- CATEGORY SETTINGS ---
    elif choice == "Category Settings":
        if user_role == "Admin":
            st.subheader("📂 Manage Categories")
            st.caption("⚠️ Only Admin is authorized to manage categories.")
            with st.expander("➕ Add"):
                n_cat = st.text_input("New Category Name", key="add_cat_input")
                if st.button("Save Category", key="add_cat_btn"): 
                    if n_cat: 
                        conn.execute('INSERT OR IGNORE INTO categories VALUES (?)', (n_cat,))
                        conn.commit(); st.toast(f"Category '{n_cat}' Added!"); st.rerun()
            with st.expander("📝 Edit"):
                c_list = [r[0] for r in conn.execute('SELECT name FROM categories').fetchall()]
                if c_list:
                    old_c = st.selectbox("Select Category", c_list, key="edit_cat_select")
                    ren_c = st.text_input("New Name", key="edit_cat_input")
                    if st.button("Update Name", key="edit_cat_btn"):
                        if ren_c: 
                            conn.execute('UPDATE categories SET name=? WHERE name=?', (ren_c, old_c))
                            conn.commit(); st.toast("Category Updated!"); st.rerun()
            with st.expander("🗑️ Delete"):
                d_list = [r[0] for r in conn.execute('SELECT name FROM categories').fetchall()]
                if d_list:
                    d_cat = st.selectbox("Remove Category", d_list, key="del_cat_select")
                    if st.button("Delete Category", key="del_cat_btn"):
                        check = conn.execute('SELECT count(*) FROM assets WHERE category=?', (d_cat,)).fetchone()[0]
                        if check == 0:
                            conn.execute('DELETE FROM categories WHERE name=?', (d_cat,))
                            conn.commit(); st.toast("Category Deleted!"); st.rerun()
                        else: st.error(f"Cannot delete! Category '{d_cat}' is in use.")
        else: st.error("Admin Only.")

    # --- LOCATION SETTINGS ---
    elif choice == "Initial Location Settings":
        if user_role == "Admin":
            st.subheader("📍 Manage Locations")
            st.caption("⚠️ Only Admin is authorized to manage locations.")
            with st.expander("➕ Add"):
                n_loc = st.text_input("New Location Name", key="add_loc_input")
                if st.button("Save Location", key="add_loc_btn"): 
                    if n_loc: 
                        conn.execute('INSERT OR IGNORE INTO locations VALUES (?)', (n_loc,))
                        conn.commit(); st.toast(f"Location '{n_loc}' Added!"); st.rerun()
            with st.expander("📝 Edit"):
                l_list = [r[0] for r in conn.execute('SELECT name FROM locations').fetchall()]
                if l_list:
                    old_l = st.selectbox("Select Location", l_list, key="edit_loc_select")
                    ren_l = st.text_input("New Name", key="edit_loc_input")
                    if st.button("Update Name", key="edit_loc_btn"):
                        if ren_l: 
                            conn.execute('UPDATE locations SET name=? WHERE name=?', (ren_l, old_l))
                            conn.commit(); st.toast("Location Updated!"); st.rerun()
            with st.expander("🗑️ Delete"):
                dl_list = [r[0] for r in conn.execute('SELECT name FROM locations').fetchall()]
                if dl_list:
                    d_loc = st.selectbox("Remove Location", dl_list, key="del_loc_select")
                    if st.button("Delete Location", key="del_loc_btn"):
                        check = conn.execute('SELECT count(*) FROM assets WHERE location=?', (d_loc,)).fetchone()[0]
                        if check == 0:
                            conn.execute('DELETE FROM locations WHERE name=?', (d_loc,))
                            conn.commit(); st.toast("Location Deleted!"); st.rerun()
                        else: st.error(f"Cannot delete! Location '{d_loc}' is in use.")
        else: st.error("Admin Only.")

    # --- USER MANAGEMENT ---
    elif choice == "User Management" and user_role == "Admin":
        st.subheader("👥 User Administration")
        st.caption("⚠️ Only Admin is authorized to manage users.")
        with st.form("user_form"):
            new_u, new_p = st.text_input("Username"), st.text_input("Password", type='password')
            new_r = st.selectbox("Role", ["Admin", "Manager", "Viewer"])
            if st.form_submit_button("Create User"):
                try:
                    conn.execute('INSERT INTO users VALUES (?,?,?)', (new_u, make_hashes(new_p), new_r))
                    conn.commit(); st.success(f"User {new_u} created!")
                except: st.error("User already exists")
        st.table(pd.read_sql('SELECT username, role FROM users', conn))

    # --- REPORTS ---
    elif choice == "Reports":
        st.header("📊 Reports")
        rep = st.radio("Type", ["Location Report", "Low Stock Alert (<= 5)"])
        df_r = pd.read_sql('SELECT * FROM assets', conn)
        if not df_r.empty:
            df_r.loc[df_r['quantity'] == 0, 'status'] = 'Out of Stock'
            df_r.loc[df_r['quantity'] > 0, 'status'] = 'In Stock'
            if rep == "Location Report":
                lo = [r[0] for r in conn.execute('SELECT name FROM locations').fetchall()]
                if lo:
                    ls = st.selectbox("Select Location", lo)
                    res = df_r[df_r['location'] == ls]
                    st.dataframe(res)
                    st.download_button(label="📥 Export Location Report (CSV)", data=res.to_csv(index=False).encode('utf-8'), file_name="location_report.csv", mime="text/csv")
            else:
                res = df_r[df_r['quantity'] <= 5]
                st.dataframe(res)
                st.download_button(label="📥 Export Low Stock Report (CSV)", data=res.to_csv(index=False).encode('utf-8'), file_name="low_stock_report.csv", mime="text/csv")
else:
    st.title("🔒 Restricted Access")
    st.info("Please enter credentials in the sidebar.")
