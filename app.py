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
    st.warning("⚠️ `streamlit-gsheets-connection` not installed. Using local fallback for subscriber data.")

def get_subscriber_data():
    """Return a dict {email: access_code} from Google Sheets or fallback."""
    if GSHEETS_AVAILABLE:
        try:
            # ⚠️ REPLACE THIS URL WITH YOUR ACTUAL SHEET URL
            url = "https://docs.google.com/spreadsheets/d/your_sheet_id_here/edit#gid=0"
            df = conn.read(spreadsheet=url, ttl="1m")
            return pd.Series(df.AccessKey.values, index=df.Email).to_dict()
        except Exception as e:
            st.error(f"Google Sheets error: {e}. Using fallback.")
            # fall through to fallback
    # --- FALLBACK: hardcoded test users or local file ---
    # Option A: Hardcoded (for testing)
    return {
        "demo@example.com": "123456",
        "engineer@test.com": "abc123"
    }
    # Option B: Read from local CSV (uncomment to use)
    # try:
    #     df = pd.read_csv("subscribers.csv")
    #     return pd.Series(df.AccessKey.values, index=df.Email).to_dict()
    # except:
    #     return {}

# --- 2. ACCELERATION‑BASED TRAVEL TIME ---
def travel_time(distance, speed, accel, jerk, use_accel):
    """Time to travel a distance (m) with given speed, acceleration, jerk."""
    if not use_accel or distance <= 0:
        return distance / speed if speed > 0 else 0
    d_acc = speed**2 / (2 * accel)
    if distance < 2 * d_acc:
        return 2 * np.sqrt(distance / accel)
    else:
        t_acc = speed / accel
        t_cruise = (distance - 2 * d_acc) / speed
        return 2 * t_acc + t_cruise

# --- 3. EXPECTED STOPS & HIGHEST REVERSAL FLOOR ---
def expected_stops_and_highest(pop_per_floor, total_passengers):
    n = len(pop_per_floor)
    if total_passengers == 0:
        return 0, 0
    prob_floor = [pop / total_passengers for pop in pop_per_floor]
    s_prob = sum(1 - (1 - prob_floor[i])**total_passengers for i in range(n))
    cum_prob = 0.0
    h_prob = 0.0
    for i in range(n):
        cum_prob += prob_floor[i]
        h_prob += 1 - (cum_prob - prob_floor[i])**total_passengers
    return s_prob, h_prob

# --- 4. MAIN LTA LOGIC ---
def run_lta_logic(inputs):
    p           = inputs['target_pop']
    n_floors    = inputs['num_floors']
    speed       = inputs['speed']
    car_cap     = inputs['car_capacity']
    floor_h     = inputs['floor_height']
    tp          = inputs['passenger_time']
    door_cycle  = inputs['t_open'] + inputs['t_dwell'] + inputs['t_close']
    zone_start  = inputs['zone_start_floor']
    use_accel   = inputs['use_accel_model']
    accel       = inputs['acceleration']
    jerk        = inputs['jerk']
    pop_per_floor = inputs['pop_per_floor']

    s_prob, h_prob = expected_stops_and_highest(pop_per_floor, p)
    if s_prob == 0:
        return {"RTT": 0, "Interval": 0, "AWT": 0, "HC": 0, "HC_persons": 0}

    travel_dist = 2 * (h_prob - zone_start) * floor_h
    travel_t = travel_time(travel_dist, speed, accel, jerk, use_accel)

    total_stops = s_prob + 1
    passenger_time = 2 * p * tp
    rtt = travel_t + total_stops * door_cycle + passenger_time

    interval = rtt / inputs['num_elevators']
    awt = interval * 0.7

    hc_persons = (car_cap * inputs['num_elevators'] * 300) / interval
    hc_percent = (hc_persons / p) * 100 if p > 0 else 0

    return {
        "RTT": round(rtt, 2),
        "Interval": round(interval, 2),
        "AWT": round(awt, 2),
        "HC": round(hc_percent, 2),
        "HC_persons": round(hc_persons, 2)
    }

# --- 5. BENCHMARK TARGET HC ---
def get_target_hc(building_type):
    targets = {
        "Office": 13,
        "Residential": 7,
        "Hotel": 9,
        "Hospital": 11
    }
    return targets.get(building_type, 10)

# --- 6. UI LAYOUT ---
st.set_page_config(page_title="LTA Pro Suite", layout="wide")

# --- SIDEBAR (subscription) ---
st.sidebar.title("🔐 Pro Access")
st.sidebar.write("Monthly License: **$59.99 USD**")
st.sidebar.markdown(f'''<a href="https://buy.stripe.com/your_link" target="_blank">
    <button style="width:100%;background-color:#1db954;color:white;border:none;padding:12px;border-radius:5px;font-weight:bold;cursor:pointer;">
        PAY NOW TO GET ACCESS CODE
    </button></a>''', unsafe_allow_html=True)

st.sidebar.divider()
user_email = st.sidebar.text_input("Registered Email").strip().lower()
user_code = st.sidebar.text_input("Enter Unique Access Code", type="password")

subscribers = get_subscriber_data()
is_pro = False
if user_email in subscribers:
    if str(subscribers[user_email]) == user_code:
        is_pro = True
        st.sidebar.success("✅ Pro Access Active")
    else:
        st.sidebar.error("❌ Invalid Code")
elif user_email != "":
    st.sidebar.warning("📧 Email not found in subscriber list.")

st.sidebar.divider()
st.sidebar.header("📋 Report Details")
st_title = st.sidebar.text_input("LTA Title", "Morning Peak Study")
st_job = st.sidebar.text_input("Project Name", "High-Rise Project")
st_no = st.sidebar.text_input("Job Number", "2026-VT-01")
st_user = st.sidebar.text_input("Creator", "Yaw Keong")

# --- MAIN INTERFACE ---
st.title("🏗️ Professional Lift Traffic Analysis")

col1, col2 = st.columns(2)
with col1:
    st.subheader("🏢 Building & Zone")
    b_type = st.selectbox("Building Type", ["Office", "Residential", "Hotel", "Hospital"])
    total_floors = st.number_input("Total Building Stories", min_value=1, value=12)
    floor_height = st.number_input("Floor‑to‑floor height (m)", min_value=2.0, max_value=6.0, value=3.5, step=0.1)

    zone_selection = "Single Zone"
    zone_start_floor = 1
    if total_floors >= 35:
        zone_selection = st.radio("Select Zone", ["Low Zone", "High Zone"], horizontal=True)
        if zone_selection == "High Zone":
            zone_start_floor = st.number_input(
                "Zone start floor (sky lobby)",
                min_value=2, max_value=total_floors-1,
                value=int(total_floors/2)+1
            )

    pop_method = st.radio("Population Input", ["Bulk", "Individual Floor"])
    if pop_method == "Bulk":
        target_pop = st.number_input("Population in this zone", min_value=1, value=400)
        served_floors = st.number_input("Floors served in this zone", min_value=1, value=total_floors if zone_selection=="Low Zone" else total_floors-zone_start_floor+1)
        pop_per_floor = [target_pop / served_floors] * served_floors
    else:
        st.caption("Enter population for **each floor** (zone start and above).")
        df_pop = st.data_editor(
            pd.DataFrame({"Floor": [f"L{i}" for i in range(1, total_floors+1)], "Pop": [0]*total_floors}),
            num_rows="dynamic",
            key="pop_editor"
        )
        df_zone = df_pop[df_pop["Floor"].str[1:].astype(int) >= zone_start_floor]
        target_pop = df_zone["Pop"].sum()
        served_floors = len(df_zone)
        pop_per_floor = df_zone["Pop"].tolist()

with col2:
    st.subheader("🚠 Elevator Setup")
    l_config = st.selectbox("Configuration", ["Simplex (1)", "Duplex (2)", "Triplex (3)"])
    num_lifts = int(l_config.split('(')[1].replace(')', ''))
    speed = st.number_input("Rated Speed (m/s)", min_value=0.5, value=1.6 if total_floors < 20 else 3.5, step=0.1)
    car_capacity = st.number_input("Car Capacity (persons)", min_value=4, max_value=26, value=13, step=1)

    with st.expander("🚪 Door & Passenger Timings"):
        t_open = st.number_input("Door Open (s)", min_value=0.5, value=4.5, step=0.1)
        t_close = st.number_input("Door Close (s)", min_value=0.5, value=4.5, step=0.1)
        t_dwell = st.number_input("Door Dwell (s)", min_value=0.0, value=3.0, step=0.1)
        tp = st.number_input("Passenger transfer time (s per person)", min_value=0.3, value=0.8, step=0.1)

    with st.expander("⚙️ Advanced Travel Time"):
        use_accel = st.checkbox("Use acceleration / jerk model", value=False)
        col_acc1, col_acc2 = st.columns(2)
        with col_acc1:
            accel = st.number_input("Acceleration (m/s²)", min_value=0.5, max_value=2.0, value=1.0, step=0.1, disabled=not use_accel)
        with col_acc2:
            jerk = st.number_input("Jerk (m/s³)", min_value=0.5, max_value=2.0, value=1.0, step=0.1, disabled=not use_accel)

inputs = {
    "num_elevators": num_lifts,
    "speed": speed,
    "car_capacity": car_capacity,
    "floor_height": floor_height,
    "passenger_time": tp,
    "t_open": t_open,
    "t_close": t_close,
    "t_dwell": t_dwell,
    "zone_start_floor": zone_start_floor,
    "target_pop": target_pop,
    "num_floors": served_floors,
    "pop_per_floor": pop_per_floor,
    "use_accel_model": use_accel,
    "acceleration": accel if use_accel else 1.0,
    "jerk": jerk if use_accel else 1.0
}

res = run_lta_logic(inputs)

st.divider()
c1, c2, c3, c4 = st.columns(4)
c1.metric("RTT", f"{res['RTT']}s")
c2.metric("Interval", f"{res['Interval']}s")

if is_pro:
    c3.metric("Avg Wait Time (AWT)", f"{res['AWT']}s")
    c4.metric("Handling Capacity", f"{res['HC']}%")
else:
    c3.warning("AWT: $59.99 Only")
    c4.warning("HC: $59.99 Only")

# --- BENCHMARK (Pro only) ---
if is_pro:
    target_hc = get_target_hc(b_type)
    st.subheader("📈 Performance against Benchmark")
    if res['HC'] >= target_hc:
        st.success(f"✅ Handling Capacity **{res['HC']}%** meets/exceeds {b_type} benchmark ({target_hc}%)")
    else:
        st.error(f"❌ Handling Capacity **{res['HC']}%** below {b_type} benchmark ({target_hc}%) – consider more / faster lifts")

# --- DISTRIBUTION GRAPH ---
st.subheader("📊 Traffic Distribution (AWT)")
fig, ax = plt.subplots(figsize=(8, 3))
data = np.random.normal(res['AWT'], res['AWT']/4, 500)
ax.hist(data, bins=30, color='#1db954', edgecolor='black', alpha=0.7)
ax.set_title(f"Wait Time Probabilities: {b_type}")
st.pyplot(fig)

# --- PRO PDF EXPORT ---
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
        pdf.cell(95, 8, f"Avg Waiting Time: {res['AWT']}s", border=1)
        pdf.cell(95, 8, f"Interval: {res['Interval']}s", border=1, ln=True)
        pdf.cell(95, 8, f"Handling Capacity: {res['HC']}%", border=1, ln=True)
        pdf.cell(95, 8, f"5‑min HC (persons): {res['HC_persons']}", border=1, ln=True)
        st.download_button("Download PDF", data=pdf.output(dest='S').encode('latin-1'), file_name=f"{st_no}_LTA.pdf")
else:
    st.error("⚠️ Monthly Payment Required for Full Metrics & PDF Reports.")
