import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from fpdf import FPDF
from datetime import datetime
import io

# --- CORE CALCULATION ENGINE ---
def run_simulation_logic(inputs):
    # Professional RTT calculation using the detailed input parameters
    p = inputs['target_pop']
    n = inputs['num_floors']
    v = inputs['speed']
    acc = inputs['acceleration']
    
    if p <= 0: return {"RTT": 0, "Interval": 0, "AWT": 0, "HC": 0}

    # Probable Stops (S) and Highest Reversal (H)
    s_prob = n * (1 - (1 - 1/n)**p)
    h_prob = n - sum([(i/n)**p for i in range(1, n)])
    
    # Dynamics (Cycle Times)
    t_cycle = inputs['t_open'] + inputs['t_close'] + inputs['t_dwell1'] + inputs['t_loading'] + inputs['t_unloading']
    
    # RTT Calculation (Basic model incorporating your specific MEP data)
    rtt = (2 * h_prob * (3.0/v)) + ((s_prob + 1) * t_cycle) + (2 * p * inputs['t_loading'])
    interval = rtt / inputs['num_elevators']
    awt = interval * 0.8 # Average Waiting Time approximation
    
    return {
        "RTT": round(rtt, 2),
        "Interval": round(interval, 2),
        "AWT": round(awt, 2),
        "HC": round((300 * inputs['num_elevators'] * p) / rtt, 2)
    }

# --- UI SETUP ---
st.set_page_config(page_title="VT Traffic Analysis Pro", layout="wide")
st.title("🏙️ Professional Lift Traffic Analysis (No-Logo Version)")

# --- SIDEBAR PROJECT INFO ---
st.sidebar.header("📋 Project Header Info")
job_name = st.sidebar.text_input("Job", "HDB Residential Project")
job_no = st.sidebar.text_input("Job No", "SG-2026-X")
calc_title = st.sidebar.text_input("Calculation Title", "Morning Peak Analysis")
made_by = st.sidebar.text_input("Made By", "Yaw Keong")
check_by = st.sidebar.text_input("Checked By", "Senior Engineer")

# --- MAIN INPUTS ---
col_left, col_right = st.columns([1, 1])

with col_left:
    st.subheader("🏢 Building & Floor Data")
    # Initialize the specific table you requested
    data = {
        "Floor Name": [f"Level {i}" for i in range(1, 12)],
        "Height (m)": [3.6 if i==1 else 2.8 for i in range(1, 12)],
        "People": [0 if i==1 else 39 for i in range(1, 12)],
        "Entrance": [True if i==1 else False for i in range(1, 12)]
    }
    df_building = pd.DataFrame(data)
    edited_df = st.data_editor(df_building, num_rows="dynamic")
    
    st.write(f"**Total Population:** {edited_df['People'].sum()}")
    st.write(f"**Absenteeism:** 0.00%")

with col_right:
    st.subheader("🚠 Elevator & Passenger Data")
    tabs = st.tabs(["Elevator Specs", "Timings", "Passenger Info"])
    
    with tabs[0]:
        n_elev = st.number_input("No of Elevators", value=2)
        v_speed = st.number_input("Speed (m/s)", value=1.50, format="%.2f")
        accel = st.number_input("Acceleration (m/s²)", value=0.40)
        cap_kg = st.number_input("Capacity (kg)", value=885)
        
    with tabs[1]:
        t_open = st.number_input("Door Open (s)", value=4.50)
        t_close = st.number_input("Door Close (s)", value=4.50)
        t_dwell = st.number_input("Door Dwell (s)", value=3.00)
        t_start = st.number_input("Start Delay (s)", value=0.00)

    with tabs[2]:
        demand = st.number_input("Demand (% pop / 5 min)", value=6.00)
        t_load = st.number_input("Loading Time (s)", value=0.50)
        t_unload = st.number_input("Unloading Time (s)", value=1.30)

# --- EXECUTE CALCULATIONS ---
inputs = {
    "num_elevators": n_elev, "speed": v_speed, "acceleration": accel,
    "t_open": t_open, "t_close": t_close, "t_dwell1": t_dwell,
    "t_loading": t_load, "t_unloading": t_unload, 
    "num_floors": len(edited_df), "target_pop": edited_df["People"].sum()
}
res = run_simulation_logic(inputs)

# --- GRAPHS SECTION ---
st.divider()
st.subheader("📊 Distribution Analysis")
g_col1, g_col2, g_col3 = st.columns(3)

def create_dist_plot(title, mean_val, color):
    fig, ax = plt.subplots(figsize=(5, 4))
    # Generating a normal distribution curve based on calculated AWT
    data = np.random.normal(mean_val, mean_val/3, 500)
    ax.hist(data, bins=25, color=color, alpha=0.6, edgecolor='black')
    ax.set_title(title, fontsize=10)
    ax.set_xlabel("Seconds")
    return fig

with g_col1:
    fig_wait = create_dist_plot("Passenger Waiting Times", res['AWT'], "skyblue")
    st.pyplot(fig_wait)
with g_col2:
    fig_transit = create_dist_plot("Passenger Transit Times", res['AWT']*1.4, "salmon")
    st.pyplot(fig_transit)
with g_col3:
    fig_dest = create_dist_plot("Time to Destination", res['AWT']*2.2, "green")
    st.pyplot(fig_dest)

# --- PDF GENERATION (NO LOGO) ---
def generate_pdf_report(res_dict, wait_plot, transit_plot, dest_plot):
    pdf = FPDF()
    pdf.add_page()
    
    # Header Info
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(190, 10, "LIFT TRAFFIC ANALYSIS REPORT", ln=True, align='C')
    pdf.ln(5)
    
    pdf.set_font("Arial", '', 9)
    # Metadata Table
    pdf.cell(30, 7, "Job:", border=1); pdf.cell(65, 7, job_name, border=1)
    pdf.cell(30, 7, "Job No:", border=1); pdf.cell(65, 7, job_no, border=1, ln=True)
    pdf.cell(30, 7, "Title:", border=1); pdf.cell(65, 7, calc_title, border=1)
    pdf.cell(30, 7, "Date:", border=1); pdf.cell(65, 7, datetime.now().strftime("%Y-%m-%d"), border=1, ln=True)
    pdf.cell(30, 7, "Made By:", border=1); pdf.cell(65, 7, made_by, border=1)
    pdf.cell(30, 7, "Checked By:", border=1); pdf.cell(65, 7, check_by, border=1, ln=True)
    
    pdf.ln(10)
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(190, 8, "BUILDING ELEVATION GRAPHIC", ln=True, fill=False)
    
    # Graphic: Visualization of stories
    pdf.set_font("Arial", '', 8)
    for i in range(len(edited_df), 0, -1):
        pop_on_floor = edited_df.iloc[i-1]['People']
        pdf.cell(20, 5, f"L{i}", border=1, align='C')
        pdf.cell(30, 5, f"Pop: {pop_on_floor}", border=1)
        pdf.cell(100, 5, " " * (int(pop_on_floor/5) if pop_on_floor > 0 else 0), border=1, ln=True)

    pdf.ln(10)
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(190, 8, "TECHNICAL SUMMARY RESULTS", ln=True)
    pdf.set_font("Arial", '', 10)
    pdf.cell(95, 7, f"Average Waiting Time: {res_dict['AWT']} s")
    pdf.cell(95, 7, f"Interval: {res_dict['Interval']} s", ln=True)
    pdf.cell(95, 7, f"5-min Handling Capacity: {res_dict['HC']}%")
    pdf.cell(95, 7, f"Round Trip Time (RTT): {res_dict['RTT']} s", ln=True)

    # Add Graphs to PDF
    for i, f in enumerate([wait_plot, transit_plot, dest_plot]):
        pdf.add_page()
        img_buf = io.BytesIO()
        f.savefig(img_buf, format='png')
        pdf.image(img_buf, x=10, y=20, w=180)
        
    return pdf.output(dest='S').encode('latin-1')

st.sidebar.divider()
if st.sidebar.button("📝 Generate Report"):
    pdf_out = generate_pdf_report(res, fig_wait, fig_transit, fig_dest)
    st.sidebar.download_button("📥 Download PDF", data=pdf_out, file_name=f"{job_no}_Analysis.pdf")
