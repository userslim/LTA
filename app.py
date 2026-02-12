import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from fpdf import FPDF
from datetime import datetime
import io

# --- ACCESS CONTROL ---
VALID_KEYS = ["PRO2026", "LTA_SG_99", "YAW_KEONG_VIP"]

# --- LTA CALCULATION ENGINE ---
def run_lta_logic(inputs):
    p = inputs['target_pop']
    n = inputs['num_floors']
    v = inputs['speed']
    
    if p <= 0 or n <= 0: 
        return {"RTT": 0, "Interval": 0, "AWT": 0, "HC": 0}

    # Probability of stops and reversal height
    s_prob = n * (1 - (1 - 1/n)**p)
    h_prob = n - sum([(i/n)**p for i in range(1, n)])
    
    # Dynamics & Zoning Logic
    t_cycle = inputs['t_open'] + inputs['t_close'] + inputs['t_dwell'] + inputs['t_load'] + inputs['t_unload']
    
    # Express Jump for High Zone (>35 floors)
    express_jump = 0
    if inputs['zone'] == "High Zone":
        # Assume jump over 15 floors if total > 35
        express_jump = (15 * 3.5) / v 
    
    # RTT Formula
    rtt = (2 * h_prob * (3.5/v)) + ((s_prob + 1) * t_cycle) + (2 * p * inputs['t_load']) + (2 * express_jump)
    interval = rtt / inputs['num_elevators']
    awt = interval * 0.6 
    
    return {
        "RTT": round(rtt, 2),
        "Interval": round(interval, 2),
        "AWT": round(awt, 2),
        "HC": round((300 * inputs['num_elevators'] * p) / rtt, 2)
    }

# --- UI SETUP ---
st.set_page_config(page_title="Professional VT Analyzer", layout="wide")

# Sidebar: Monetization
st.sidebar.title("🔐 Pro Subscription")
st.sidebar.markdown("[💳 Pay Monthly Subscription ($50)](https://buy.stripe.com/your_link)")
access_key = st.sidebar.text_input("Enter Pro Access Key", type="password")
is_pro = access_key in VALID_KEYS

# Sidebar: Project Header
st.sidebar.divider()
st.sidebar.header("📋 Project Details")
job_name = st.sidebar.text_input("Job", "35+ Storey Project")
job_no = st.sidebar.text_input("Job No", "2026-SG-VT")
made_by = st.sidebar.text_input("Made By", "Yaw Keong")

st.title("🏗️ High-Rise Lift Traffic Analysis (35+ Floors)")

# --- INPUT SECTION ---
col1, col2 = st.columns(2)

with col1:
    st.subheader("🏢 Building & Zoning")
    zone_type = st.radio("Zoning Selection", ["Low Zone", "High Zone"], horizontal=True)
    
    pop_method = st.radio("Population Input Method", ["Overall Population", "Individual Floor Input"])
    
    if pop_method == "Overall Population":
        total_pop = st.number_input("Enter Total Population", value=500)
        num_floors = st.number_input("Total Floors Served", value=35)
        # Placeholder for calc
        pop_per_floor = total_pop / num_floors
        df_building = pd.DataFrame({"Floor": [f"L{i}" for i in range(1, int(num_floors)+1)], "People": [pop_per_floor]*int(num_floors)})
    else:
        st.info("Add/Remove rows below for specific floor data")
        df_building = st.data_editor(pd.DataFrame({
            "Floor Name": ["Level 1", "Level 2"],
            "People": [0, 40]
        }), num_rows="dynamic")
        total_pop = df_building["People"].sum()
        num_floors = len(df_building)

with col2:
    st.subheader("🚠 Elevator Configuration")
    config = st.selectbox("Elevator Bank Type", ["Simplex (1)", "Duplex (2)", "Triplex (3)"])
    n_elev = int(config.split('(')[1].replace(')', ''))
    
    v_speed = st.number_input("Rated Speed (m/s)", value=3.5 if num_floors > 35 else 1.6, step=0.5)
    
    with st.expander("Advanced MEP Data"):
        t_open = st.number_input("Door Open (s)", value=4.5)
        t_close = st.number_input("Door Close (s)", value=4.5)
        t_dwell = st.number_input("Door Dwell (s)", value=3.0)
        t_load = st.number_input("Loading (s)", value=0.5)
        t_unload = st.number_input("Unloading (s)", value=1.3)

# --- RUN CALCULATIONS ---
calc_inputs = {
    "num_elevators": n_elev, "speed": v_speed, "zone": zone_type,
    "t_open": t_open, "t_close": t_close, "t_dwell": t_dwell,
    "t_load": t_load, "t_unload": t_unload,
    "num_floors": num_floors, "target_pop": total_pop
}
res = run_lta_logic(calc_inputs)

# --- DISPLAY RESULTS ---
st.divider()
st.subheader("📊 Performance Results")
r1, r2, r3, r4 = st.columns(4)
r1.metric("RTT", f"{res['RTT']}s")
r2.metric("Interval", f"{res['Interval']}s")

if is_pro:
    r3.metric("Avg Wait Time (AWT)", f"{res['AWT']}s")
    r4.metric("Handling Cap", f"{res['HC']}%")
    
    # Graphs
    st.subheader("📈 Distributions")
    g1, g2 = st.columns(2)
    
    def make_plot(val, label):
        fig, ax = plt.subplots(figsize=(5, 3))
        ax.hist(np.random.normal(val, val/4, 200), color='skyblue', edgecolor='black')
        ax.set_title(label)
        return fig

    fig_wait = make_plot(res['AWT'], "Distribution of Waiting Times")
    fig_transit = make_plot(res['AWT']*1.5, "Distribution of Transit Times")
    g1.pyplot(fig_wait); g2.pyplot(fig_transit)

    # --- PDF GENERATOR (Fixed Error Version) ---
    if st.button("Generate Pro PDF Report"):
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", 'B', 14)
        pdf.cell(190, 10, "LIFT TRAFFIC ANALYSIS REPORT", ln=True, align='C')
        pdf.ln(5)
        pdf.set_font("Arial", '', 10)
        pdf.cell(190, 8, f"Project: {job_name} | Job No: {job_no}", ln=True)
        pdf.cell(190, 8, f"Zoning: {zone_type} | Config: {config}", ln=True)
        pdf.ln(5)
        pdf.set_font("Arial", 'B', 11)
        pdf.cell(190, 8, f"RESULT: AWT {res['AWT']}s", ln=True)
        
        pdf_bytes = pdf.output(dest='S')
        if not isinstance(pdf_bytes, bytes):
            pdf_bytes = pdf_bytes.encode('latin-1')
            
        st.download_button("📥 Download PDF", data=pdf_bytes, file_name="VT_Report.pdf")
else:
    st.warning("🔒 Monthly Payment Required for AWT, Handling Capacity, and PDF Reports.")
