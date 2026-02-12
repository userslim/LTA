import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from fpdf import FPDF
from datetime import datetime
import io

# --- 1. ACCESS CONTROL DATABASE (MANUAL UPDATE) ---
# Each email is mapped to ONE unique code. 
# You update this list when you receive a Stripe payment notification.
SUBSCRIBER_DATABASE = {
    "engineer1@company.com": "LTA-7742-XP",
    "consultant@mep-sg.com": "LTA-9012-ZZ",
    "test@user.com": "12345" # For your own testing
}

PAYMENT_URL = "https://buy.stripe.com/your_link_for_59_99"

# --- 2. LTA CALCULATION ENGINE ---
def run_lta_logic(inputs):
    p, n, v = inputs['target_pop'], inputs['num_floors'], inputs['speed']
    if p <= 0 or n <= 0: return {"RTT": 0, "Interval": 0, "AWT": 0, "HC": 0}

    # CIBSE Guide D logic
    s_prob = n * (1 - (1 - 1/n)**p)
    h_prob = n - sum([(i/n)**p for i in range(1, n)])
    t_cycle = inputs['t_open'] + inputs['t_close'] + inputs['t_dwell'] + inputs['t_load'] + inputs['t_unload']
    
    express_jump = 0
    if inputs['is_high_zone']:
        # High zone skips 50% of the building height
        express_jump = ((inputs['total_bldg_floors'] / 2) * 3.5) / v
    
    rtt = (2 * h_prob * (3.5/v)) + ((s_prob + 1) * t_cycle) + (2 * p * inputs['t_load']) + (2 * express_jump)
    interval = rtt / inputs['num_elevators']
    awt = interval * 0.7 
    
    return {
        "RTT": round(rtt, 2), "Interval": round(interval, 2),
        "AWT": round(awt, 2), "HC": round((300 * inputs['num_elevators'] * p) / rtt, 2)
    }

# --- 3. UI LAYOUT ---
st.set_page_config(page_title="LTA Pro Suite", layout="wide")

# Sidebar: Monetization
st.sidebar.title("🔐 Pro Access")
st.sidebar.write("Monthly License: **$59.99 USD**")
st.sidebar.markdown(f'''<a href="{PAYMENT_URL}" target="_blank">
    <button style="width:100%;background-color:#1db954;color:white;border:none;padding:12px;border-radius:5px;font-weight:bold;cursor:pointer;">
        PAY NOW TO GET ACCESS CODE
    </button></a>''', unsafe_allow_html=True)

st.sidebar.divider()
user_email = st.sidebar.text_input("Enter Registered Email")
user_code = st.sidebar.text_input("Enter Unique Access Code", type="password")

# Validation Logic
is_pro = False
if user_email in SUBSCRIBER_DATABASE:
    if SUBSCRIBER_DATABASE[user_email] == user_code:
        is_pro = True
        st.sidebar.success("✅ Pro Access Active")
    else:
        st.sidebar.error("❌ Invalid Code for this Email")

# Report Headers
st.sidebar.divider()
st.sidebar.header("📋 Report Headers")
st_title = st.sidebar.text_input("LTA Title", "Peak Hour Analysis")
st_job = st.sidebar.text_input("Project Name", "High-Rise Alpha")
st_no = st.sidebar.text_input("Job Number", "2026-VT-001")
st_user = st.sidebar.text_input("Creator", "Yaw Keong")

st.title("🏗️ Professional Lift Traffic Analysis")

# --- 4. BUILDING & ELEVATOR INPUTS ---
col1, col2 = st.columns(2)
with col1:
    st.subheader("🏢 Building Specification")
    b_type = st.selectbox("Building Type", ["Office (Prestige)", "Office (Standard)", "Residential (HDB/Private)", "Hotel", "Hospital"])
    total_floors = st.number_input("Total Building Stories", min_value=1, value=12)
    
    # Zone Selection Logic (Enabled only for 35+ floors)
    zone_selection = "Single Zone"
    if total_floors >= 35:
        zone_selection = st.radio("Select Zone", ["Low Zone", "High Zone"], horizontal=True)
    else:
        st.info("Zoning disabled for buildings under 35 floors.")

    pop_method = st.radio("Population Entry", ["Bulk Population", "By Floor Individual"])
    if pop_method == "Bulk Population":
        target_pop = st.number_input("Total Population in Zone", value=400)
        served_floors = st.number_input("Floors Served", value=total_floors)
    else:
        df_pop = st.data_editor(pd.DataFrame({"Floor": [f"L{i}" for i in range(1, total_floors+1)], "Pop": [30]*total_floors}), num_rows="dynamic")
        target_pop = df_pop["Pop"].sum()
        served_floors = len(df_pop)

with col2:
    st.subheader("🚠 Elevator Setup")
    l_config = st.selectbox("Configuration", ["Simplex (1)", "Duplex (2)", "Triplex (3)"])
    num_lifts = int(l_config.split('(')[1].replace(')', ''))
    speed = st.number_input("Rated Speed (m/s)", value=1.6 if total_floors < 20 else 3.5, step=0.5)
    
    with st.expander("Mechanical Timings"):
        t_open = st.number_input("Door Open (s)", value=4.5)
        t_close = st.number_input("Door Close (s)", value=4.5)
        t_dwell = st.number_input("Door Dwell (s)", value=3.0)
        t_load = st.number_input("Loading Time (s)", value=0.5)
        t_unload = st.number_input("Unloading Time (s)", value=1.3)

# Calculate
res = run_lta_logic({
    "num_elevators": num_lifts, "speed": speed, "total_bldg_floors": total_floors,
    "num_floors": served_floors, "target_pop": target_pop, "is_high_zone": (zone_selection == "High Zone"),
    "t_open": t_open, "t_close": t_close, "t_dwell": t_dwell, "t_load": t_load, "t_unload": t_unload
})

# --- 5. RESULTS & GRAPHS ---
st.divider()
c1, c2, c3, c4 = st.columns(4)
c1.metric("RTT", f"{res['RTT']}s")
c2.metric("Interval", f"{res['Interval']}s")

if is_pro:
    c3.metric("Avg Wait Time (AWT)", f"{res['AWT']}s")
    c4.metric("Handling Cap", f"{res['HC']}%")
else:
    c3.warning("AWT: $59.99 Only")
    c4.warning("HC: $59.99 Only")

st.subheader("📊 Traffic Distribution (AWT Graph)")
# Graph is visible to everyone as a "teaser" of the app's power
fig, ax = plt.subplots(figsize=(8, 3))
data = np.random.normal(res['AWT'], res['AWT']/4, 500)
ax.hist(data, bins=30, color='#1db954', edgecolor='black', alpha=0.7)
ax.set_title(f"Wait Time Probability for {b_type}")
ax.set_xlabel("Wait Time (Seconds)")
st.pyplot(fig)

# PDF Generation (PRO Only)
if is_pro:
    if st.button("📥 Generate Pro PDF Report"):
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", 'B', 14)
        pdf.cell(190, 10, st_title, ln=True, align='C')
        pdf.set_font("Arial", '', 10)
        pdf.cell(95, 8, f"Project: {st_job}", border=1); pdf.cell(95, 8, f"Job No: {st_no}", border=1, ln=True)
        pdf.cell(95, 8, f"Created By: {st_user}", border=1); pdf.cell(95, 8, f"Date: {datetime.now().strftime('%Y-%m-%d')}", border=1, ln=True)
        pdf.ln(10)
        pdf.set_font("Arial", 'B', 12); pdf.cell(190, 10, "TECHNICAL SUMMARY", ln=True)
        pdf.set_font("Arial", '', 10)
        pdf.cell(95, 8, f"Avg Waiting Time: {res['AWT']}s", border=1); pdf.cell(95, 8, f"Interval: {res['Interval']}s", border=1, ln=True)
        pdf.cell(95, 8, f"Handling Capacity: {res['HC']}%", border=1, ln=True)
        st.download_button("Download Now", data=pdf.output(dest='S').encode('latin-1'), file_name=f"{st_no}_LTA.pdf")
else:
    st.error("⚠️ Monthly Payment Required for Full Metrics & PDF Exports.")
