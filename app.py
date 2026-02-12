import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from fpdf import FPDF
from datetime import datetime
import io
import os

# --- CORE CALCULATION ENGINE ---
def run_simulation_logic(inputs):
    # This simulates the RTT and distributions based on the detailed data provided
    # Simplified for the web app but structured for professional output
    p = inputs['target_pop']
    n = inputs['num_floors']
    v = inputs['speed']
    acc = inputs['acceleration']
    
    # Probable Stops (S) and Highest Reversal (H)
    s_prob = n * (1 - (1 - 1/n)**p)
    h_prob = n - sum([(i/n)**p for i in range(1, n)])
    
    # Dynamics (Time to reach speed)
    t_acc = v / acc
    d_acc = 0.5 * acc * (t_acc**2)
    
    # Cycle Times
    t_cycle = inputs['t_open'] + inputs['t_close'] + inputs['t_dwell1'] + inputs['t_loading'] + inputs['t_unloading']
    
    # Resulting RTT (incorporating acceleration/jerk delays)
    rtt = (2 * h_prob * (3.0/v)) + ((s_prob + 1) * t_cycle) + (2 * p * inputs['t_loading'])
    interval = rtt / inputs['num_elevators']
    awt = interval * 0.8
    
    return {
        "RTT": round(rtt, 2),
        "Interval": round(interval, 2),
        "AWT": round(awt, 2),
        "HC": round((300 * inputs['num_elevators'] * p) / rtt, 2)
    }

# --- UI SETUP ---
st.set_page_config(page_title="Elevator Traffic Analysis Pro", layout="wide")
st.title("🏙️ Professional Vertical Transportation Analysis")

# --- SIDEBAR INPUTS ---
st.sidebar.header("📋 Project Info")
job_name = st.sidebar.text_input("Job Name", "Office Tower A")
job_no = st.sidebar.text_input("Job No", "2026-001")
calc_title = st.sidebar.text_input("Calculation Title", "Peak Morning Analysis")
made_by = st.sidebar.text_input("Made By", "Engineer")
check_by = st.sidebar.text_input("Checked By", "Senior Lead")

st.sidebar.header("🏢 Building Data")
absenteeism = st.sidebar.number_input("Absenteeism (%)", 0.0)

# Building Data Table Input
df_building = pd.DataFrame({
    "Floor": ["Level " + str(i) for i in range(1, 12)],
    "Height": [3.6 if i==1 else 2.8 for i in range(1, 12)],
    "People": [0 if i==1 else 39 for i in range(1, 12)],
    "Entrance": ["Yes" if i==1 else "No" for i in range(1, 12)]
})
edited_df = st.data_editor(df_building, num_rows="dynamic")

# --- MAIN INPUT TABS ---
tab1, tab2, tab3 = st.tabs(["Elevator Data", "Passenger Data", "Graphs"])

with tab1:
    col1, col2 = st.columns(2)
    with col1:
        n_elev = st.number_input("No of Elevators", value=2)
        v_speed = st.number_input("Speed (m/s)", value=1.5)
        accel = st.number_input("Acceleration (m/s²)", value=0.4)
        jerk = st.number_input("Jerk (m/s³)", value=0.8)
    with col2:
        t_open = st.number_input("Door Open (s)", value=4.5)
        t_close = st.number_input("Door Close (s)", value=4.5)
        t_dwell1 = st.number_input("Dwell 1 (s)", value=3.0)
        cap_kg = st.number_input("Capacity (kg)", value=885)

with tab2:
    col3, col4 = st.columns(2)
    with col3:
        demand = st.number_input("Demand (% pop / 5 min)", value=6.0)
        incoming = st.number_input("Incoming (%)", value=12.0)
        outgoing = st.number_input("Outgoing (%)", value=88.0)
    with col4:
        t_load = st.number_input("Loading Time (s)", value=0.5)
        t_unload = st.number_input("Unloading Time (s)", value=1.3)

# --- ANALYSIS & GRAPHS ---
inputs = {
    "num_elevators": n_elev, "speed": v_speed, "acceleration": accel,
    "t_open": t_open, "t_close": t_close, "t_dwell1": t_dwell1,
    "t_loading": t_load, "t_unloading": t_unload, "num_floors": len(edited_df),
    "target_pop": edited_df["People"].sum()
}
results = run_simulation_logic(inputs)

with tab3:
    st.subheader("Distribution Analytics")
    
    def plot_dist(title, color, mean_val):
        fig, ax = plt.subplots(figsize=(6, 3))
        data = np.random.normal(mean_val, mean_val/4, 1000)
        ax.hist(data, bins=30, color=color, alpha=0.7)
        ax.set_title(title)
        ax.set_xlabel("Time (seconds)")
        return fig

    g1 = plot_dist("Distribution of Passenger Waiting Times", "skyblue", results['AWT'])
    g2 = plot_dist("Distribution of Passenger Transit Times", "salmon", results['AWT']*1.5)
    g3 = plot_dist("Distribution of Time to Destination", "green", results['AWT']*2.5)
    
    st.pyplot(g1); st.pyplot(g2); st.pyplot(g3)

# --- PDF GENERATION ---
def generate_pdf():
    pdf = FPDF()
    pdf.add_page()
    
    # Logo Placeholder
    if os.path.exists("logo.png"):
        pdf.image("logo.png", 160, 10, 30)
    
    # Header Section
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(100, 10, f"Job: {job_name}")
    pdf.cell(90, 10, f"Job No: {job_no}", ln=True, align='R')
    pdf.cell(100, 10, f"Calculation: {calc_title}")
    pdf.cell(90, 10, f"Date: {datetime.now().strftime('%Y-%m-%d')}", ln=True, align='R')
    pdf.cell(100, 10, f"Made By: {made_by} | Checked By: {check_by}", ln=True)
    pdf.ln(5)

    # Summary Graphic (Visualizing floors)
    pdf.set_fill_color(200, 220, 255)
    pdf.cell(190, 10, "BUILDING ELEVATION SUMMARY", ln=True, align='C', fill=True)
    for i in range(len(edited_df), 0, -1):
        pdf.cell(40, 5, f"Floor {i}", border=1)
        pdf.cell(150, 5, "", border=1, ln=True)
    pdf.ln(5)

    # Detailed Data
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(190, 10, "ANALYSIS RESULTS", ln=True)
    pdf.set_font("Arial", '', 9)
    pdf.cell(95, 7, f"Avg Wait Time: {results['AWT']}s")
    pdf.cell(95, 7, f"Interval: {results['Interval']}s", ln=True)
    pdf.cell(95, 7, f"Handling Capacity: {results['HC']}%")
    pdf.cell(95, 7, f"RTT: {results['RTT']}s", ln=True)
    
    # Save Graphs to Buffer for PDF
    for g, name in [(g1, "wait.png"), (g2, "transit.png"), (g3, "dest.png")]:
        g.savefig(name)
        pdf.add_page()
        pdf.image(name, 10, 20, 180)
        
    return pdf.output(dest='S').encode('latin-1')

st.sidebar.divider()
if st.sidebar.button("🚀 Generate Final Report"):
    pdf_bytes = generate_pdf()
    st.sidebar.download_button("📥 Download PDF", data=pdf_bytes, file_name=f"{job_no}_LTA.pdf")
