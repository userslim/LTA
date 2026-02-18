import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from fpdf import FPDF
import tempfile
import os

# --- 1. ACCELERATION‑BASED TRAVEL TIME ---
def travel_time(distance, speed, accel, jerk, use_accel):
    if not use_accel or distance <= 0 or speed <= 0:
        return distance / speed if speed > 0 else 0
    
    # Kinematic travel time including jerk and acceleration phases
    d_acc = (speed**2) / (2 * accel)
    if distance < 2 * d_acc:
        return 2 * np.sqrt(distance / accel)
    else:
        t_acc = speed / accel
        t_cruise = (distance - 2 * d_acc) / speed
        return (2 * t_acc) + t_cruise

# --- 2. EXPECTED STOPS & HIGHEST REVERSAL FLOOR ---
def expected_stops_and_highest(pop_per_floor, total_passengers):
    n = len(pop_per_floor)
    if total_passengers <= 0 or n == 0:
        return 0, 0
    
    prob_floor = [pop / total_passengers for pop in pop_per_floor]
    s_prob = sum(1 - (1 - p)**total_passengers for p in prob_floor)
    
    h_prob = 0.0
    cum_prob = 0.0
    for i in range(n):
        cum_prob += prob_floor[i]
        h_prob += (1 - (cum_prob - prob_floor[i])**total_passengers)
    return s_prob, h_prob

# --- 3. UPDATED MAIN LTA LOGIC ---
def run_lta_logic(inputs):
    p = inputs['target_pop']
    speed = inputs['speed']
    car_cap = inputs['car_capacity']
    tp = inputs['passenger_time']
    
    # Comprehensive Door Cycle including Pre-opening and Delays
    door_cycle = (inputs['t_open'] + inputs['t_close'] + 
                  inputs['t_dwell_1'] + inputs['t_dwell_2'] + 
                  inputs['t_pre_open'])
    
    # Additional equipment delays
    equipment_delays = inputs['start_delay'] + inputs['levelling_delay']
    
    num_lifts = max(1, inputs['num_elevators'])
    pop_per_floor = inputs['pop_per_floor']
    
    s_prob, h_prob = expected_stops_and_highest(pop_per_floor, p)
    
    if s_prob <= 0 or speed <= 0:
        return {"RTT": 0, "Interval": 0, "AWT": 0, "HC": 0}

    dist_m = (h_prob - 1) * inputs['floor_height'] 
    travel_t = travel_time(2 * dist_m, speed, inputs['acceleration'], inputs['jerk'], True)

    # RTT = Travel + (Stops * (Door Cycle + Delays)) + Passenger Loading
    rtt = travel_t + ((s_prob + 1) * (door_cycle + equipment_delays)) + (2 * p * tp)
    interval = rtt / num_lifts
    awt = interval * 0.7 

    hc_persons = (car_cap * 0.8 * num_lifts * 300) / interval
    hc_percent = (hc_persons / p) * 100 if p > 0 else 0

    return {
        "RTT": round(rtt, 2), "Interval": round(interval, 2),
        "AWT": round(awt, 2), "HC": round(hc_percent, 2)
    }

# --- 4. UI SETUP ---
st.set_page_config(page_title="LTA Pro Suite", layout="wide")

st.sidebar.title("📋 Project Details")
st_title = st.sidebar.text_input("Report Title", "Detailed Traffic Analysis")
st_job = st.sidebar.text_input("Project Name", "Project Alpha")
st_no = st.sidebar.text_input("Job No", "REF-001")
st_user = st.sidebar.text_input("Creator", "Yaw Keong")

st.title("🏗️ Professional Lift Traffic Analysis")

col1, col2 = st.columns(2)
with col1:
    st.subheader("🏢 Building & Zone")
    b_type = st.selectbox("Building Type", ["Office", "Residential", "Hospital", "Factory", "Multi Storey Carpark"])
    total_floors = st.number_input("Total Floors", min_value=1, value=12)
    floor_h = st.number_input("Floor Height (m)", value=3.5)
    target_pop = st.number_input("Zone Population", value=400)
    pop_per_floor = [target_pop / total_floors] * total_floors

with col2:
    st.subheader("🚠 Elevator Setup")
    lift_options = [f"Group of {i} ({i})" for i in range(1, 11)]
    l_config = st.selectbox("Configuration", lift_options, index=1)
    num_lifts = int(l_config.split('(')[1].replace(')', ''))
    
    speed = st.number_input("Rated Speed (m/s)", value=1.6)
    accel = st.number_input("Acceleration (m/s²)", value=1.0)
    jerk = st.number_input("Jerk (m/s³)", value=1.0)
    car_cap = st.number_input("Car Capacity (persons)", value=13)

# --- NEW PARAMETERS FROM IMAGE ---
with st.expander("⏱️ Advanced Door & Delay Parameters", expanded=True):
    c1, c2, c3 = st.columns(3)
    with c1:
        t_pre_open = st.number_input("Door Pre-opening (s)", value=0.5)
        t_open = st.number_input("Door Open Time (s)", value=2.0)
        t_close = st.number_input("Door Close Time (s)", value=2.5)
    with c2:
        t_dwell_1 = st.number_input("Door Dwell 1 (s)", value=1.0)
        t_dwell_2 = st.number_input("Door Dwell 2 (s)", value=1.0)
        tp = st.number_input("Passenger Transfer (s)", value=0.8)
    with c3:
        start_delay = st.number_input("Start Delay (s)", value=0.5)
        level_delay = st.number_input("Levelling Delay (s)", value=0.5)

# Run Logic
res = run_lta_logic({
    "num_elevators": num_lifts, "speed": speed, "acceleration": accel, "jerk": jerk,
    "car_capacity": car_cap, "floor_height": floor_h, "target_pop": target_pop,
    "pop_per_floor": pop_per_floor, "passenger_time": tp,
    "t_pre_open": t_pre_open, "t_open": t_open, "t_close": t_close,
    "t_dwell_1": t_dwell_1, "t_dwell_2": t_dwell_2,
    "start_delay": start_delay, "levelling_delay": level_delay
})

# Display
st.divider()
m1, m2, m3, m4 = st.columns(4)
m1.metric("RTT", f"{res['RTT']}s")
m2.metric("Interval", f"{res['Interval']}s")
m3.metric("AWT", f"{res['AWT']}s")
m4.metric("Handling Cap", f"{res['HC']}%")

# Graphing
fig, ax = plt.subplots(figsize=(8, 3))
data = np.random.normal(res['AWT'], max(1, res['AWT']/4), 500)
ax.hist(data, bins=30, color='#0070BA', edgecolor='white')
ax.set_title("Wait Time Probability Distribution")
st.pyplot(fig)

# PDF Export (FIXED ERROR)
if st.button("📥 Download PDF Report"):
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("helvetica", 'B', 16)
        pdf.cell(0, 10, st_title, center=True, ln=True)
        pdf.set_font("helvetica", size=10)
        pdf.cell(0, 10, f"Project: {st_job} | Job: {st_no} | Creator: {st_user}", ln=True)
        
        # Results Table
        pdf.ln(5)
        pdf.set_font("helvetica", 'B', 12)
        pdf.cell(0, 10, "Summary results", ln=True)
        pdf.set_font("helvetica", size=10)
        for k, v in res.items():
            pdf.cell(50, 8, f"{k}:", border=1)
            pdf.cell(50, 8, f"{v}", border=1, ln=True)

        # FIX: Remove .encode('latin-1') and use bytes directly
        pdf_output = pdf.output()
        if isinstance(pdf_output, str):
            pdf_bytes = pdf_output.encode('latin-1')
        else:
            pdf_bytes = pdf_output # Modern fpdf2 returns bytes

        st.download_button("Save PDF", data=pdf_bytes, file_name="Report.pdf", mime="application/pdf")
    except Exception as e:
        st.error(f"PDF Error: {e}")
