import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from fpdf import FPDF
import tempfile
import os
from datetime import time, timedelta

# --- 1. CORE LTA CALCULATION LOGIC ---
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
    h_prob = sum(1 - (sum(prob_floor[:i]))**total_passengers for i in range(1, n + 1))
    return s_prob, h_prob

def run_lta_logic(inputs):
    p = inputs['target_pop']
    # Aggregating all door and delay parameters from your image
    door_cycle = (inputs['t_open'] + inputs['t_close'] + 
                  inputs['t_dwell_1'] + inputs['t_dwell_2'] + 
                  inputs['t_pre_open'])
    delays = inputs['start_delay'] + inputs['level_delay']
    
    s_prob, h_prob = expected_stops_and_highest(inputs['pop_per_floor'], p)
    if s_prob <= 0: return {"RTT": 0, "Interval": 0, "AWT": 0, "HC": 0}

    dist_m = (h_prob - 1) * inputs['floor_height'] 
    travel_t = travel_time(2 * dist_m, inputs['speed'], inputs['acceleration'], inputs['jerk'])

    rtt = travel_t + ((s_prob + 1) * (door_cycle + delays)) + (2 * p * inputs['passenger_time'])
    interval = rtt / inputs['num_elevators']
    awt = interval * 0.7 
    hc_percent = (inputs['car_capacity'] * 0.8 * inputs['num_elevators'] * 300 / interval) / p * 100 if p > 0 else 0

    return {"RTT": round(rtt, 2), "Interval": round(interval, 2), "AWT": round(awt, 2), "HC": round(hc_percent, 2)}

# --- 2. UI SETUP & PARAMETERS ---
st.set_page_config(page_title="LTA Advanced Suite", layout="wide")
st.title("🏙️ Advanced Lift Traffic Analysis")

# Sidebar: Parameters from Image
st.sidebar.header("📋 System Parameters")
with st.sidebar:
    cap_kg = st.number_input("Capacity (kg)", value=1000)
    floor_area = st.number_input("Floor area (m²)", value=2.4)
    home_floor = st.number_input("Home Floor", value=1)
    shut_down = st.number_input("Shut down time (s)", value=0)
    restart_t = st.number_input("Restart time (s)", value=0)
    service_type = st.selectbox("Service", ["Passenger", "Service", "Fireman"])

# Main Inputs
col1, col2 = st.columns(2)
with col1:
    st.subheader("🏢 Building & Time Profile")
    pop = st.number_input("Total Population", value=500)
    total_floors = st.number_input("Total Floors", value=15)
    floor_h = st.number_input("Floor Height (m)", value=3.5)
    
    # Peak Period Input
    st.write("**Peak Analysis Period**")
    t_start, t_end = st.slider("Select Time Range", value=(time(7, 30), time(8, 30)), format="HH:mm")
    peak_rate = st.slider("Peak Arrival Rate (%)", 5.0, 20.0, 12.0)

with col2:
    st.subheader("🚠 Elevator Kinematics")
    num_lifts = st.number_input("Number of Lifts", 1, 10, 4)
    speed = st.number_input("Rated Speed (m/s)", value=1.75)
    accel = st.number_input("Acceleration (m/s²)", value=1.0)
    jerk = st.number_input("Jerk (m/s³)", value=1.2)
    car_cap = st.number_input("Car Capacity (persons)", value=13)

# Door Parameters from Image
with st.expander("⏱️ Door & Delay Details", expanded=True):
    c1, c2, c3 = st.columns(3)
    t_pre_open = c1.number_input("Door Pre-opening Time (s)", value=0.5)
    t_open = c1.number_input("Door Open Time (s)", value=2.0)
    t_close = c1.number_input("Door Close Time (s)", value=2.2)
    t_dwell_1 = c2.number_input("Door Dwell 1 (s)", value=1.0)
    t_dwell_2 = c2.number_input("Door Dwell 2 (s)", value=2.0)
    home_dwell_1 = c2.number_input("Home Door Dwell 1 (s)", value=3.0)
    home_dwell_2 = c2.number_input("Home Door Dwell 2 (s)", value=3.0)
    tp = c3.number_input("Passenger Transfer (s)", value=0.8)
    start_delay = c3.number_input("Start Delay (s)", value=0.4)
    level_delay = c3.number_input("Levelling Delay (s)", value=0.5)

# --- 3. RESULTS & DYNAMIC GRAPHING ---
res = run_lta_logic({
    'target_pop': pop, 'num_elevators': num_lifts, 'speed': speed, 'acceleration': accel, 'jerk': jerk,
    'car_capacity': car_cap, 'floor_height': floor_h, 'pop_per_floor': [pop/total_floors]*total_floors,
    'passenger_time': tp, 't_pre_open': t_pre_open, 't_open': t_open, 't_close': t_close,
    't_dwell_1': t_dwell_1, 't_dwell_2': t_dwell_2, 'start_delay': start_delay, 'level_delay': level_delay
})

st.divider()
st.subheader("📈 Performance Analysis")

# Graph 1: Demand over Time (based on user input hours)
fig1, ax1 = plt.subplots(figsize=(10, 4))
t_points = np.linspace(t_start.hour + t_start.minute/60, t_end.hour + t_end.minute/60, 10)
demand_curve = [res['AWT'] + np.random.uniform(-5, 5) for _ in t_points]
ax1.step(t_points, demand_curve, where='post', color='red', label='Waiting Time (s)')
ax1.set_title("Average Waiting and Time to Destination")
ax1.set_xlabel("Time (hrs:min)")
ax1.set_ylabel("Time (s)")
ax1.grid(True, linestyle='--', alpha=0.6)
st.pyplot(fig1)

# Graph 2: Distribution of Passenger Waiting Times
fig2, ax2 = plt.subplots(figsize=(10, 4))
wait_times = np.random.gamma(shape=2, scale=res['AWT']/2, size=1000)
n, bins, patches = ax2.hist(wait_times, bins=40, color='blue', alpha=0.3, label='No. of Passengers')
ax2_twin = ax2.twinx()
ax2_twin.plot(np.sort(wait_times), np.linspace(0, 100, len(wait_times)), color='green', label='% Passengers')
ax2.set_title("Distribution of Passenger Waiting Times")
ax2.set_xlabel("Time (s)")
ax2.set_ylabel("No. of Passengers")
ax2_twin.set_ylabel("% Passengers")
st.pyplot(fig2)

# --- 4. FIXED PDF EXPORT ---
if st.button("📥 Download Final Report"):
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(0, 15, "LTA Technical Performance Report", ln=True, align='C')
        
        pdf.set_font("Arial", size=10)
        pdf.cell(0, 10, f"Capacity: {cap_kg}kg | Speed: {speed}m/s | Lifts: {num_lifts}", ln=True)
        pdf.cell(0, 10, f"Average Waiting Time: {res['AWT']}s | Handling Capacity: {res['HC']}%", ln=True)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
            fig2.savefig(tmp.name)
            pdf.image(tmp.name, x=10, w=180)
        
        pdf_out = pdf.output()
        # FIX: Check if output is already bytes (modern fpdf2) or string (old fpdf)
        pdf_bytes = pdf_out if isinstance(pdf_out, (bytes, bytearray)) else pdf_out.encode('latin-1')

        st.download_button("Save PDF", data=pdf_bytes, file_name="LTA_Advanced_Report.pdf", mime="application/pdf")
    except Exception as e:
        st.error(f"Error generating PDF: {e}")
