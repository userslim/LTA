import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from fpdf import FPDF
from datetime import datetime
import io

# --- ACCESS CONTROL (Your Subscription Revenue) ---
VALID_KEYS = ["PRO2026", "LTA_SG_VIP", "YAW_KEONG_99"]

def run_lta_logic(inputs):
    p = inputs['target_pop']
    n = inputs['num_floors']
    v = inputs['speed']
    
    if p <= 0 or n <= 0: 
        return {"RTT": 0, "Interval": 0, "AWT": 0, "HC": 0}

    # Probability based on population and floors
    s_prob = n * (1 - (1 - 1/n)**p)
    h_prob = n - sum([(i/n)**p for i in range(1, n)])
    
    # Timing Constants
    t_cycle = inputs['t_open'] + inputs['t_close'] + inputs['t_dwell'] + inputs['t_load'] + inputs['t_unload']
    
    # High Zone Express Jump Logic
    express_jump = 0
    if inputs['is_high_zone']:
        # Express jump assumes skipping approximately 50% of the building height
        express_jump = ( (inputs['total_bldg_floors'] / 2) * 3.5) / v
    
    # Round Trip Time (RTT) and Interval
    rtt = (2 * h_prob * (3.5/v)) + ((s_prob + 1) * t_cycle) + (2 * p * inputs['t_load']) + (2 * express_jump)
    interval = rtt / inputs['num_elevators']
    awt = interval * 0.7  # Industry standard AWT estimation
    
    return {
        "RTT": round(rtt, 2),
        "Interval": round(interval, 2),
        "AWT": round(awt, 2),
        "HC": round((300 * inputs['num_elevators'] * p) / rtt, 2)
    }

# --- UI APP SETUP ---
st.set_page_config(page_title="LTA Professional Suite", layout="wide")

# Sidebar: Monthly Payment & License
st.sidebar.title("💳 Subscription")
st.sidebar.info("PDF Reports and Data Metrics require a Pro Key.")
access_key = st.sidebar.text_input("Enter Access Key", type="password")
is_pro = access_key in VALID_KEYS

# Sidebar: Project Headers (Requested)
st.sidebar.divider()
st.sidebar.header("📄 Report Header Info")
proj_name = st.sidebar.text_input("Project Name", "New Development")
proj_no = st.sidebar.text_input("Project Number", "2026-001")
lta_title = st.sidebar.text_input("LTA Title", "Peak Traffic Study")
creator = st.sidebar.text_input("Creator / Made By", "Yaw Keong")
report_date = st.sidebar.date_input("Date", datetime.now())

st.title("🏙️ Lift Traffic Analysis Professional Suite")

# --- MAIN INPUT SECTION ---
col1, col2 = st.columns(2)

with col1:
    st.subheader("🏢 Building & Floors")
    total_floors = st.number_input("Total Building Stories", min_value=1, value=12)
    
    # 35-Floor Logic: Disable Zoning for smaller buildings
    if total_floors >= 35:
        zone_selection = st.radio("Select Zone to Analyze", ["Low Zone", "High Zone"], horizontal=True)
        st.success("Zoning Enabled (Building > 35 Stories)")
    else:
        zone_selection = "Single Zone"
        st.info("Zoning Disabled (Building < 35 Stories)")

    pop_method = st.radio("Population Entry", ["Bulk Population", "By Floor"])
    if pop_method == "Bulk Population":
        target_pop = st.number_input("Total Population in Zone", value=400)
        served_floors = st.number_input("Number of Floors Served", value=total_floors)
    else:
        df_pop = st.data_editor(pd.DataFrame({"Floor": [f"L{i}" for i in range(1, total_floors+1)], "Pop": [30]*total_floors}), num_rows="dynamic")
        target_pop = df_pop["Pop"].sum()
        served_floors = len(df_pop)

with col2:
    st.subheader("🚠 Elevator Configuration")
    l_type = st.selectbox("Elevator Bank", ["Simplex (1)", "Duplex (2)", "Triplex (3)"])
    num_lifts = int(l_type.split('(')[1].replace(')', ''))
    speed = st.number_input("Rated Speed (m/s)", value=1.6 if total_floors < 20 else 3.5, step=0.5)
    
    with st.expander("Mechanical Timings"):
        t_open = st.number_input("Door Open (s)", value=4.5)
        t_close = st.number_input("Door Close (s)", value=4.5)
        t_dwell = st.number_input("Door Dwell (s)", value=3.0)
        t_load = st.number_input("Loading Time (s)", value=0.5)
        t_unload = st.number_input("Unloading Time (s)", value=1.3)

# --- CALCULATIONS ---
is_high_zone = (zone_selection == "High Zone")
res = run_lta_logic({
    "num_elevators": num_lifts, "speed": speed, "total_bldg_floors": total_floors,
    "num_floors": served_floors, "target_pop": target_pop, "is_high_zone": is_high_zone,
    "t_open": t_open, "t_close": t_close, "t_dwell": t_dwell, "t_load": t_load, "t_unload": t_unload
})

# --- RESULTS DISPLAY ---
st.divider()
st.subheader("📊 Performance Analytics")
c1, c2, c3, c4 = st.columns(4)
c1.metric("RTT", f"{res['RTT']}s")
c2.metric("Interval", f"{res['Interval']}s")

# Paywall for numerical data
if is_pro:
    c3.metric("Avg Wait Time (AWT)", f"{res['AWT']}s")
    c4.metric("Handling Cap", f"{res['HC']}%")
else:
    c3.warning("AWT: PRO Only")
    c4.warning("HC: PRO Only")

# --- GRAPHS (Always visible to entice users to pay) ---
st.subheader("📈 Traffic Distribution (AWT)")
fig, ax = plt.subplots(figsize=(8, 3))
data = np.random.normal(res['AWT'], res['AWT']/4, 500)
ax.hist(data, bins=30, color='skyblue', edgecolor='black', alpha=0.7)
ax.axvline(res['AWT'], color='red', linestyle='dashed', linewidth=2, label=f"Mean AWT: {res['AWT']}s")
ax.set_title("Distribution of Passenger Waiting Times")
ax.set_xlabel("Wait Time (Seconds)")
ax.legend()
st.pyplot(fig)

# --- PRO PDF EXPORT ---
if is_pro:
    if st.button("📥 Generate Pro PDF Report"):
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", 'B', 14)
        pdf.cell(190, 10, lta_title, ln=True, align='C')
        pdf.set_font("Arial", '', 10)
        pdf.cell(95, 8, f"Project: {proj_name}", border=1)
        pdf.cell(95, 8, f"Job No: {proj_no}", border=1, ln=True)
        pdf.cell(95, 8, f"Creator: {creator}", border=1)
        pdf.cell(95, 8, f"Date: {report_date}", border=1, ln=True)
        pdf.ln(10)
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(190, 10, "LTA RESULTS SUMMARY", ln=True)
        pdf.set_font("Arial", '', 10)
        pdf.cell(95, 8, f"Avg Waiting Time: {res['AWT']}s", border=1)
        pdf.cell(95, 8, f"Handling Capacity: {res['HC']}%", border=1, ln=True)
        
        pdf_bytes = pdf.output(dest='S')
        if not isinstance(pdf_bytes, bytes): pdf_bytes = pdf_bytes.encode('latin-1')
        st.download_button("Click to Download", data=pdf_bytes, file_name=f"{proj_no}_LTA.pdf")
else:
    st.error("⚠️ Monthly Payment Required for AWT, Handling Capacity, and PDF Reports")
