import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from fpdf import FPDF
from datetime import datetime
import io

# --- 1. GOOGLE SHEETS CONNECTION (with fallback) ---
try:
    from streamlit_gsheets import GSheetsConnection
    conn = st.connection("gsheets", type=GSheetsConnection)
    GSHEETS_AVAILABLE = True
except ImportError:
    GSHEETS_AVAILABLE = False

def get_subscriber_data():
    if GSHEETS_AVAILABLE:
        try:
            # ⚠️ REPLACE WITH YOUR REAL URL
            url = "https://docs.google.com/spreadsheets/d/your_sheet_id_here/edit#gid=0"
            df = conn.read(spreadsheet=url, ttl="1m")
            return pd.Series(df.AccessKey.values, index=df.Email).to_dict()
        except:
            pass
    return {"demo@example.com": "123456", "engineer@test.com": "abc123"}

# --- 2. ACCELERATION‑BASED TRAVEL TIME ---
def travel_time(distance, speed, accel, jerk, use_accel):
    if not use_accel or distance <= 0 or speed <= 0:
        return distance / speed if speed > 0 else 0
    
    # Simple Kinematic check: Distance to reach full speed
    d_acc = (speed**2) / (2 * accel)
    if distance < 2 * d_acc:
        return 2 * np.sqrt(distance / accel)
    else:
        t_acc = speed / accel
        t_cruise = (distance - 2 * d_acc) / speed
        return (2 * t_acc) + t_cruise

# --- 3. EXPECTED STOPS & HIGHEST REVERSAL FLOOR ---
def expected_stops_and_highest(pop_per_floor, total_passengers):
    n = len(pop_per_floor)
    if total_passengers <= 0 or n == 0:
        return 0, 0
    
    # Industry Standard: Probabilistic model for stops (S) and Reversal Floor (H)
    prob_floor = [pop / total_passengers for pop in pop_per_floor]
    s_prob = sum(1 - (1 - p)**total_passengers for p in prob_floor)
    
    # Highest Reversal Floor (H) Calculation
    h_prob = 0.0
    cum_prob = 0.0
    for i in range(n):
        cum_prob += prob_floor[i]
        h_prob += (1 - (cum_prob - prob_floor[i])**total_passengers)
    return s_prob, h_prob

# --- 4. MAIN LTA LOGIC ---
def run_lta_logic(inputs):
    p = inputs['target_pop']
    speed = inputs['speed']
    car_cap = inputs['car_capacity']
    tp = inputs['passenger_time']
    door_cycle = inputs['t_open'] + inputs['t_dwell'] + inputs['t_close']
    zone_start = inputs['zone_start_floor']
    pop_per_floor = inputs['pop_per_floor']

    s_prob, h_prob = expected_stops_and_highest(pop_per_floor, p)
    
    if s_prob <= 0 or speed <= 0:
        return {"RTT": 0, "Interval": 0, "AWT": 0, "HC": 0, "HC_persons": 0}

    # Travel Time: Express jump to sky lobby + floor-to-floor transit
    # distance to reversal floor minus the starting floor
    dist_m = (h_prob - 1) * inputs['floor_height'] 
    travel_t = travel_time(2 * dist_m, speed, inputs['acceleration'], inputs['jerk'], inputs['use_accel_model'])

    # Total RTT = Travel Time + Door cycles + Passenger boarding/exiting
    rtt = travel_t + ((s_prob + 1) * door_cycle) + (2 * p * tp)
    interval = rtt / inputs['num_elevators']
    awt = interval * 0.7

    hc_persons = (car_cap * 0.8 * inputs['num_elevators'] * 300) / interval # 80% load factor
    hc_percent = (hc_persons / p) * 100 if p > 0 else 0

    return {
        "RTT": round(rtt, 2), "Interval": round(interval, 2),
        "AWT": round(awt, 2), "HC": round(hc_percent, 2), "HC_persons": round(hc_persons, 2)
    }

# --- 5. UI SETUP ---
st.set_page_config(page_title="LTA Pro Suite", layout="wide")

# Sidebar
st.sidebar.title("🔐 Pro Access")
st.sidebar.markdown(f'''<a href="https://buy.stripe.com/your_link" target="_blank">
    <button style="width:100%;background-color:#1db954;color:white;border:none;padding:12px;border-radius:5px;font-weight:bold;cursor:pointer;">
        PAY $59.99 FOR ACCESS CODE
    </button></a>''', unsafe_allow_html=True)

st.sidebar.divider()
user_email = st.sidebar.text_input("Registered Email").strip().lower()
user_code = st.sidebar.text_input("Access Code", type="password")

subscribers = get_subscriber_data()
is_pro = (user_email in subscribers and str(subscribers[user_email]) == user_code)
if is_pro: st.sidebar.success("✅ Pro Access Active")
elif user_email: st.sidebar.error("❌ Invalid Access")

# Report Details
st.sidebar.header("📋 Report Headers")
st_title = st.sidebar.text_input("LTA Title", "Morning Peak Analysis")
st_job = st.sidebar.text_input("Project Name", "New Building")
st_no = st.sidebar.text_input("Job No", "2026-01")
st_user = st.sidebar.text_input("Creator", "Yaw Keong")

st.title("🏗️ Professional Lift Traffic Analysis")

col1, col2 = st.columns(2)
with col1:
    st.subheader("🏢 Building & Zone")
    b_type = st.selectbox("Building Type", ["Office", "Residential", "Hotel", "Hospital"])
    total_floors = st.number_input("Total Floors", min_value=1, value=12)
    floor_h = st.number_input("Floor Height (m)", value=3.5)

    zone_start = 1
    if total_floors >= 35:
        zone = st.radio("Zoning", ["Low Zone", "High Zone"], horizontal=True)
        if zone == "High Zone":
            zone_start = st.number_input("Sky Lobby Floor", value=int(total_floors/2)+1)

    pop_method = st.radio("Pop Input", ["Bulk", "Individual"])
    if pop_method == "Bulk":
        target_pop = st.number_input("Zone Population", value=400)
        served = st.number_input("Floors Served", value=total_floors - zone_start + 1)
        pop_per_floor = [target_pop / served] * int(served)
    else:
        df_pop = st.data_editor(pd.DataFrame({"Floor": [f"L{i}" for i in range(zone_start, total_floors+1)], "Pop": [30.0]*(total_floors-zone_start+1)}), num_rows="dynamic")
        target_pop = df_pop["Pop"].sum()
        pop_per_floor = df_pop["Pop"].tolist()

with col2:
    st.subheader("🚠 Elevator Setup")
    l_config = st.selectbox("Configuration", ["Simplex (1)", "Duplex (2)", "Triplex (3)"])
    num_lifts = int(l_config.split('(')[1].replace(')', ''))
    speed = st.number_input("Rated Speed (m/s)", value=1.6)
    car_cap = st.number_input("Car Capacity (persons)", value=13)

    with st.expander("⚙️ Advanced Timings & Kinematics"):
        tp = st.number_input("Passenger Transfer (s)", value=0.8)
        t_open = st.number_input("Door Open (s)", value=2.0)
        t_close = st.number_input("Door Close (s)", value=2.5)
        t_dwell = st.number_input("Door Dwell (s)", value=1.0)
        use_accel = st.checkbox("Enable Accel/Jerk Model", value=True)
        accel = st.number_input("Acceleration (m/s²)", value=1.0, disabled=not use_accel)
        jerk = st.number_input("Jerk (m/s³)", value=1.0, disabled=not use_accel)

# Run Calculation
res = run_lta_logic({
    "num_elevators": num_lifts, "speed": speed, "car_capacity": car_cap,
    "floor_height": floor_h, "passenger_time": tp, "t_open": t_open,
    "t_close": t_close, "t_dwell": t_dwell, "zone_start_floor": zone_start,
    "target_pop": target_pop, "num_floors": len(pop_per_floor), 
    "pop_per_floor": pop_per_floor, "use_accel_model": use_accel,
    "acceleration": accel, "jerk": jerk
})

# Display Metrics
st.divider()
m1, m2, m3, m4 = st.columns(4)
m1.metric("RTT", f"{res['RTT']}s")
m2.metric("Interval", f"{res['Interval']}s")

if is_pro:
    m3.metric("AWT", f"{res['AWT']}s")
    m4.metric("Handling Cap", f"{res['HC']}%")
    
    # Benchmarking
    targets = {"Office": 13, "Residential": 7, "Hotel": 9, "Hospital": 11}
    target = targets.get(b_type, 10)
    if res['HC'] >= target: st.success(f"✅ Meets {b_type} benchmark ({target}%)")
    else: st.error(f"❌ Below {b_type} benchmark ({target}%)")
else:
    m3.warning("AWT: $59.99 Only")
    m4.warning("HC: $59.99 Only")

# Distribution Graph
if res['AWT'] > 0:
    st.subheader("📊 Wait Time Distribution")
    fig, ax = plt.subplots(figsize=(8, 3))
    data = np.random.normal(res['AWT'], res['AWT']/4 if res['AWT'] > 0 else 1, 500)
    ax.hist(data, bins=30, color='#1db954', edgecolor='black', alpha=0.7)
    st.pyplot(fig)

# PDF Export (using fpdf2 logic)
if is_pro and st.button("📥 Download Pro Report"):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("helvetica", 'B', 16)
    pdf.cell(0, 10, st_title, center=True, new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("helvetica", size=10)
    pdf.cell(0, 10, f"Project: {st_job} | Job No: {st_no} | Creator: {st_user}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(10)
    pdf.cell(0, 10, f"Resulting AWT: {res['AWT']}s", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 10, f"Handling Capacity: {res['HC']}%", new_x="LMARGIN", new_y="NEXT")
    
    # Correct way to handle bytes for Streamlit download
    pdf_bytes = pdf.output() 
    st.download_button("Click to Download", data=pdf_bytes, file_name=f"{st_no}_LTA.pdf", mime="application/pdf")
