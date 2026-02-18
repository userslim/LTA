import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from fpdf import FPDF
import tempfile
import os

# --- 1. KINEMATIC & TRAFFIC LOGIC ---
def travel_time(distance, speed, accel, jerk):
    if distance <= 0 or speed <= 0: return 0
    d_acc = (speed**2) / (2 * accel)
    if distance < 2 * d_acc:
        return 2 * np.sqrt(distance / accel)
    else:
        t_acc = speed / accel
        t_cruise = (distance - 2 * d_acc) / speed
        return (2 * t_acc) + t_cruise

def expected_stops_and_highest(pop_per_floor, total_passengers):
    n = len(pop_per_floor)
    if total_passengers <= 0 or n == 0: return 0, 0
    prob_floor = [pop / total_passengers for pop in pop_per_floor]
    s_prob = sum(1 - (1 - p)**total_passengers for p in prob_floor)
    h_prob = 0.0
    cum_prob = 0.0
    for i in range(n):
        cum_prob += prob_floor[i]
        h_prob += (1 - (cum_prob - prob_floor[i])**total_passengers)
    return s_prob, h_prob

def run_lta_logic(inputs):
    p = inputs['target_pop']
    # Total Door Cycle from your provided parameter list
    door_cycle = (inputs['t_open'] + inputs['t_close'] + 
                  inputs['t_dwell_1'] + inputs['t_dwell_2'] + 
                  inputs['t_pre_open'])
    
    # Equipment Delays
    delays = inputs['start_delay'] + inputs['level_delay']
    
    s_prob, h_prob = expected_stops_and_highest(inputs['pop_per_floor'], p)
    if s_prob <= 0: return {"RTT": 0, "Interval": 0, "AWT": 0, "HC": 0}

    dist_m = (h_prob - 1) * inputs['floor_height'] 
    travel_t = travel_time(2 * dist_m, inputs['speed'], inputs['acceleration'], inputs['jerk'])

    # RTT Calculation
    rtt = travel_t + ((s_prob + 1) * (door_cycle + delays)) + (2 * p * inputs['passenger_time'])
    interval = rtt / inputs['num_elevators']
    awt = interval * 0.7 
    hc_percent = (inputs['car_capacity'] * 0.8 * inputs['num_elevators'] * 300 / interval) / p * 100 if p > 0 else 0

    return {"RTT": round(rtt, 2), "Interval": round(interval, 2), "AWT": round(awt, 2), "HC": round(hc_percent, 2)}

# --- 2. UI SETUP ---
st.set_page_config(page_title="Professional LTA Suite", layout="wide")
st.title("🏗️ Lift Traffic Analysis & Demand Modeling")

# --- SIDEBAR: SYSTEM PARAMETERS (FROM IMAGE) ---
st.sidebar.header("⚙️ System Parameters")
with st.sidebar:
    # Adding parameters from the provided image
    cap_kg = st.number_input("Capacity (kg)", value=1000)
    floor_area = st.number_input("Floor area (m²)", value=2.4)
    home_floor = st.number_input("Home Floor", value=1)
    shut_down = st.number_input("Shut down time (s)", value=0)
    restart_t = st.number_input("Restart time (s)", value=0)
    
    st.divider()
    paypal_url = "https://www.paypal.com/paypalme/YOUR_USERNAME"
    st.markdown(f'[Donate via PayPal]({paypal_url})')

# --- MAIN INPUTS ---
col1, col2 = st.columns(2)
with col1:
    st.subheader("🏢 Building & Demand")
    total_floors = st.number_input("Total Floors", value=12)
    pop = st.number_input("Total Population", value=400)
    floor_h = st.number_input("Floor Height (m)", value=3.5)
    # Peak Hour Demand Input
    peak_rate = st.slider("Peak Arrival Rate (% of Pop / 5 min)", 5.0, 25.0, 12.0)

with col2:
    st.subheader("🚠 Elevator Setup")
    num_lifts = st.number_input("Number of Lifts", 1, 10, 3)
    speed = st.number_input("Rated Speed (m/s)", value=1.6)
    accel = st.number_input("Acceleration (m/s²)", value=1.0)
    jerk = st.number_input("Jerk (m/s³)", value=1.0)
    car_cap = st.number_input("Car Capacity (persons)", value=13)

with st.expander("⏱️ Door Timings (from Parameters List)", expanded=True):
    c1, c2, c3 = st.columns(3)
    t_pre_open = c1.number_input("Door Pre-opening (s)", value=0.5)
    t_open = c1.number_input("Door Open Time (s)", value=2.0)
    t_close = c1.number_input("Door Close Time (s)", value=2.5)
    t_dwell_1 = c2.number_input("Door Dwell 1 (s)", value=1.0)
    t_dwell_2 = c2.number_input("Door Dwell 2 (s)", value=1.0)
    tp = c2.number_input("Passenger Transfer (s)", value=0.8)
    start_delay = c3.number_input("Start Delay (s)", value=0.5)
    level_delay = c3.number_input("Levelling Delay (s)", value=0.5)

# Calculations
res = run_lta_logic({
    'target_pop': pop, 'num_elevators': num_lifts, 'speed': speed, 'acceleration': accel, 'jerk': jerk,
    'car_capacity': car_cap, 'floor_height': floor_h, 'pop_per_floor': [pop/total_floors]*total_floors,
    'passenger_time': tp, 't_pre_open': t_pre_open, 't_open': t_open, 't_close': t_close,
    't_dwell_1': t_dwell_1, 't_dwell_2': t_dwell_2, 'start_delay': start_delay, 'level_delay': level_delay
})

# --- 3. DEMAND GRAPH ---
st.divider()
st.subheader("📈 Passenger Demand & Wait Time Analysis")
g1, g2 = st.columns(2)

# Demand Graph (Normal Distribution centered on Peak)
with g1:
    hours = np.linspace(7, 10, 100) # 7 AM to 10 AM
    demand = peak_rate * np.exp(-0.5 * ((hours - 8.5) / 0.4)**2) # Peak at 8:30 AM
    fig1, ax1 = plt.subplots(figsize=(6, 4))
    ax1.plot(hours, demand, color='tab:red', linewidth=2)
    ax1.fill_between(hours, demand, color='tab:red', alpha=0.3)
    ax1.set_title("Morning Peak Demand Profile")
    ax1.set_xlabel("Time of Day")
    ax1.set_ylabel("Arrival Rate (%)")
    st.pyplot(fig1)

# Wait Time Distribution
with g2:
    wait_data = np.random.normal(res['AWT'], res['AWT']/4, 500)
    fig2, ax2 = plt.subplots(figsize=(6, 4))
    ax2.hist(wait_data, bins=25, color='#0070BA', edgecolor='white')
    ax2.set_title(f"Wait Time Distribution (Avg: {res['AWT']}s)")
    st.pyplot(fig2)

# Results Metrics
m1, m2, m3, m4 = st.columns(4)
m1.metric("RTT", f"{res['RTT']}s")
m2.metric("Interval", f"{res['Interval']}s")
m3.metric("AWT", f"{res['AWT']}s")
m4.metric("Handling Cap", f"{res['HC']}%")

# --- 4. EXPORT ---
if st.button("📥 Download Technical Report"):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, "LTA Technical Report", ln=True, align='C')
    pdf.set_font("Arial", size=10)
    pdf.ln(10)
    
    # Summary of all parameters from the image
    pdf.cell(0, 10, f"System Specs: Capacity: {cap_kg}kg | Area: {floor_area}m2 | Home Floor: {home_floor}", ln=True)
    pdf.cell(0, 10, f"RTT: {res['RTT']}s | Interval: {res['Interval']}s | AWT: {res['AWT']}s", ln=True)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
        fig1.savefig(tmp.name)
        pdf.image(tmp.name, x=10, y=50, w=90)
    
    pdf_out = pdf.output()
    # Check for string vs bytes for different FPDF versions
    pdf_bytes = pdf_out.encode('latin-1') if isinstance(pdf_out, str) else pdf_out
    st.download_button("Save PDF", data=pdf_bytes, file_name="LTA_Report.pdf")
