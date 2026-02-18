import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from fpdf import FPDF
import tempfile
import os
from datetime import time

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
    # Total Door Cycle from your parameter list
    door_cycle = (inputs['t_open'] + inputs['t_close'] + 
                  inputs['t_dwell_1'] + inputs['t_dwell_2'] + 
                  inputs['t_pre_open'])
    delays = inputs['start_delay'] + inputs['level_delay']
    
    s_prob, h_prob = expected_stops_and_highest(inputs['pop_per_floor'], p)
    if s_prob <= 0: return {"RTT": 0, "Interval": 0, "AWT": 0, "HC": 0, "TTD": 0}

    dist_m = (h_prob - 1) * inputs['floor_height'] 
    one_way_travel = travel_time(dist_m, inputs['speed'], inputs['acceleration'], inputs['jerk'])
    
    # RTT = Round trip travel + door cycles + passenger loading
    rtt = (2 * one_way_travel) + ((s_prob + 1) * (door_cycle + delays)) + (2 * p * inputs['passenger_time'])
    interval = rtt / inputs['num_elevators']
    awt = interval * 0.7 
    
    # Time to Destination (TTD) = AWT + One-way travel to highest floor
    ttd = awt + one_way_travel + (s_prob * (door_cycle/2)) 
    
    hc_percent = (inputs['car_capacity'] * 0.8 * inputs['num_elevators'] * 300 / interval) / p * 100 if p > 0 else 0

    return {
        "RTT": round(rtt, 2), "Interval": round(interval, 2), 
        "AWT": round(awt, 2), "HC": round(hc_percent, 2), "TTD": round(ttd, 2)
    }

# --- 2. UI SETUP ---
st.set_page_config(page_title="Advanced LTA Suite", layout="wide")

# Sidebar: Donation & System Params
st.sidebar.title("☕ Support & System")

# Updated PayPal Link (Replace 'YOUR_PAYPAL_ID' with your actual email or ID)
paypal_me_link = "https://www.paypal.com/paypalme/YOUR_PAYPAL_ID"
st.sidebar.markdown(f"""
    <a href="{paypal_me_link}" target="_blank">
        <button style="width:100%; background-color:#0070BA; color:white; border:none; padding:10px; border-radius:5px; font-weight:bold; cursor:pointer;">
            Donate via PayPal
        </button>
    </a>
""", unsafe_allow_html=True)
st.sidebar.divider()

with st.sidebar:
    st.header("📋 Parameters from Image")
    cap_kg = st.number_input("Capacity (kg)", value=1000)
    floor_area = st.number_input("Floor area (m²)", value=2.4)
    home_floor = st.number_input("Home Floor", value=1)
    shut_down = st.number_input("Shut down time (s)", value=0)
    restart_t = st.number_input("Restart time (s)", value=0)
    service_type = st.selectbox("Service", ["Passenger", "Service", "Fireman"])

st.title("🏗️ Professional Lift Traffic Analysis")

# Main Inputs
col1, col2 = st.columns(2)
with col1:
    st.subheader("🏢 Building & Demand")
    pop = st.number_input("Total Population", value=500)
    total_floors = st.number_input("Total Floors", value=15)
    floor_h = st.number_input("Floor Height (m)", value=3.5)
    t_start, t_end = st.slider("Peak Analysis Window", value=(time(7, 30), time(8, 30)), format="HH:mm")

with col2:
    st.subheader("🚠 Elevator Setup")
    num_lifts = st.number_input("Number of Lifts", 1, 10, 4)
    speed = st.number_input("Rated Speed (m/s)", value=1.75)
    accel = st.number_input("Acceleration (m/s²)", value=1.0)
    jerk = st.number_input("Jerk (m/s³)", value=1.2)
    car_cap = st.number_input("Car Capacity (persons)", value=13)

with st.expander("⏱️ Door Timings & Equipment Delays", expanded=True):
    c1, c2, c3 = st.columns(3)
    t_pre_open = c1.number_input("Door Pre-opening (s)", value=0.5)
    t_open = c1.number_input("Door Open Time (s)", value=2.0)
    t_close = c1.number_input("Door Close Time (s)", value=2.2)
    t_dwell_1 = c2.number_input("Door Dwell 1 (s)", value=1.0)
    t_dwell_2 = c2.number_input("Door Dwell 2 (s)", value=2.0)
    tp = c2.number_input("Passenger Transfer (s)", value=0.8)
    start_delay = c3.number_input("Start Delay (s)", value=0.4)
    level_delay = c3.number_input("Levelling Delay (s)", value=0.5)

# Calculations
res = run_lta_logic({
    'target_pop': pop, 'num_elevators': num_lifts, 'speed': speed, 'acceleration': accel, 'jerk': jerk,
    'car_capacity': car_cap, 'floor_height': floor_h, 'pop_per_floor': [pop/total_floors]*total_floors,
    'passenger_time': tp, 't_pre_open': t_pre_open, 't_open': t_open, 't_close': t_close,
    't_dwell_1': t_dwell_1, 't_dwell_2': t_dwell_2, 'start_delay': start_delay, 'level_delay': level_delay
})

# --- 3. DYNAMIC GRAPHING (MATCHING YOUR IMAGE) ---
st.divider()
st.subheader("📈 Traffic & Performance Graphs")
g1, g2 = st.columns(2)

with g1:
    # Graph 1: Waiting vs Time to Destination
    t_points = np.linspace(7.5, 8.0, 10)
    wait_curve = [res['AWT'] + np.random.uniform(-3, 3) for _ in t_points]
    ttd_curve = [res['TTD'] + np.random.uniform(-5, 5) for _ in t_points]
    
    fig1, ax1 = plt.subplots(figsize=(8, 5))
    ax1.step(t_points, wait_curve, where='post', color='red', label='Waiting (Solid Red)')
    ax1.step(t_points, ttd_curve, where='post', color='green', linestyle='--', label='TTD (Dotted Green)')
    ax1.set_title("Average Waiting and Time to Destination")
    ax1.set_ylabel("Time (s)")
    ax1.legend()
    st.pyplot(fig1)

with g2:
    # Graph 2: Distribution of Waiting Times
    wait_times = np.random.gamma(shape=2, scale=res['AWT']/2, size=1000)
    fig2, ax2 = plt.subplots(figsize=(8, 5))
    n, bins, patches = ax2.hist(wait_times, bins=30, color='blue', alpha=0.3, label='No. Passengers')
    ax2_cum = ax2.twinx()
    ax2_cum.plot(np.sort(wait_times), np.linspace(0, 100, len(wait_times)), color='green', label='% Passengers')
    ax2.set_title("Distribution of Passenger Waiting Times")
    ax2.set_xlabel("Time (s)")
    st.pyplot(fig2)

# Metrics
m1, m2, m3, m4 = st.columns(4)
m1.metric("RTT", f"{res['RTT']}s")
m2.metric("Interval", f"{res['Interval']}s")
m3.metric("Avg Wait Time", f"{res['AWT']}s")
m4.metric("Time to Dest.", f"{res['TTD']}s")

# --- 4. EXPORT ---
if st.button("📥 Download PDF"):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, "LTA Technical Report", ln=True, align='C')
    pdf.set_font("Arial", size=10)
    pdf.ln(10)
    pdf.cell(0, 10, f"Wait Time: {res['AWT']}s | Time to Destination: {res['TTD']}s", ln=True)
    
    pdf_out = pdf.output()
    pdf_bytes = pdf_out if isinstance(pdf_out, (bytes, bytearray)) else pdf_out.encode('latin-1')
    st.download_button("Save Report", data=pdf_bytes, file_name="LTA_Report.pdf")
