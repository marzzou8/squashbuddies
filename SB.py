#!/usr/bin/env python
# coding: utf-8

# In[26]:

import datetime
import requests
import pandas as pd
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials


# -----------------------------
# CONFIG
# -----------------------------
SPREADSHEET_ID = "15RMyE21x8OmcJ35_lqNEanSVuygB3Khpk2r83BiJ654"
DEFAULT_TIME_SLOT = "2–5pm"
DEFAULT_FEE = 4  # payment amount when marking paid

EXPECTED_COLUMNS = [
    "Date", "Player Name", "Paid", "Court", "Time Slot",
    "Collection", "Expense", "Balance", "Description"
]


# -----------------------------
# SECRETS
# -----------------------------
TELEGRAM_TOKEN = st.secrets["TELEGRAM_TOKEN"]
CHAT_ID = st.secrets["CHAT_ID"]

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


# -----------------------------
# GOOGLE SHEETS AUTH
# -----------------------------
creds = Credentials.from_service_account_info(
    st.secrets["gcp_service_account"],
    scopes=SCOPES
)
gc = gspread.authorize(creds)
worksheet = gc.open_by_key(SPREADSHEET_ID).sheet1  # recommended unique ID method


# -----------------------------
# HELPERS
# -----------------------------
def get_next_sundays(n=6):
    today = datetime.date.today()
    days_until_sunday = (6 - today.weekday()) % 7
    first_sunday = today + datetime.timedelta(days=days_until_sunday)
    return [first_sunday + datetime.timedelta(weeks=i) for i in range(n)]


def ensure_headers():
    """Ensure row 1 matches EXPECTED_COLUMNS (without deleting data rows)."""
    header = worksheet.row_values(1)
    header = [h.strip() for h in header] if header else []

    if not header:
        worksheet.insert_row(EXPECTED_COLUMNS, 1)
        return

    if header != EXPECTED_COLUMNS:
        # Update the header row in place (keep existing rows)
        worksheet.update("A1:I1", [EXPECTED_COLUMNS])  # 9 columns


@st.cache_data(ttl=30, show_spinner=False)
def load_records_cached(cache_bust: int = 0) -> pd.DataFrame:
    """Load records from Google Sheet with stable schema + _row for edits/deletes."""
    ensure_headers()

    values = worksheet.get_all_values()
    if len(values) <= 1:
        df = pd.DataFrame(columns=EXPECTED_COLUMNS)
        df["_row"] = pd.Series(dtype=int)
        return df

    header = [h.strip() for h in values[0]]
    rows = values[1:]

    df = pd.DataFrame(rows, columns=header)

    # Guarantee schema
    for col in EXPECTED_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    df = df[EXPECTED_COLUMNS]

    # Track actual sheet row numbers (data starts at row 2)
    df["_row"] = range(2, 2 + len(df))

    # Type conversions
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce").dt.date

    def to_bool(x):
        s = str(x).strip().lower()
        return s in ("true", "1", "yes", "y")

    df["Paid"] = df["Paid"].apply(to_bool)

    for c in ["Collection", "Expense", "Balance"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)

    df["Court"] = pd.to_numeric(df["Court"], errors="coerce")

    # Normalize strings
    for c in ["Player Name", "Time Slot", "Description"]:
        df[c] = df[c].astype(str).replace("nan", "").fillna("").str.strip()

    return df


def bust_cache():
    st.session_state["_cache_bust"] = st.session_state.get("_cache_bust", 0) + 1


def load_records() -> pd.DataFrame:
    return load_records_cached(st.session_state.get("_cache_bust", 0))


def send_telegram_message(message: str):
    """Send message to Telegram and show error if it fails."""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message}
    resp = requests.post(url, json=payload, timeout=10)  # json payload pattern
    if resp.status_code != 200:
        st.error(f"Telegram error: {resp.text}")


def append_record(record: dict):
    """Append a new record row to Google Sheet with Balance = Collection - Expense."""
    collection = float(record.get("Collection", 0) or 0)
    expense = float(record.get("Expense", 0) or 0)
    record["Balance"] = collection - expense

    row = []
    for col in EXPECTED_COLUMNS:
        val = record.get(col, "")
        if isinstance(val, (datetime.date, datetime.datetime)):
            val = val.strftime("%Y-%m-%d")
        if val is None:
            val = ""
        row.append(val)

    worksheet.append_row(row, value_input_option="USER_ENTERED")


def update_row_cells(sheet_row: int, updates: dict):
    """Update specific columns for a given row."""
    header = [h.strip() for h in worksheet.row_values(1)]
    col_map = {name: idx + 1 for idx, name in enumerate(header)}  # 1-based

    cells = []
    for k, v in updates.items():
        if k not in col_map:
            continue
        col = col_map[k]
        if isinstance(v, bool):
            v = "TRUE" if v else "FALSE"
        cells.append(gspread.Cell(sheet_row, col, v))

    if cells:
        worksheet.update_cells(cells, value_input_option="USER_ENTERED")


def delete_sheet_rows(row_numbers):
    """Delete multiple rows safely (bottom-up)."""
    for r in sorted([int(x) for x in row_numbers], reverse=True):
        worksheet.delete_rows(r)


def build_dashboard_message(df: pd.DataFrame, target_date: datetime.date) -> str:
    """Build message identical to dashboard summary: courts + attendance + all-time finance."""
    sunday_df = df[df["Date"] == target_date]

    attendance_df = sunday_df[sunday_df["Description"].str.lower() == "attendance"]
    court_df = sunday_df[sunday_df["Description"].str.lower() == "court booking"]

    lines = []
    lines.append(f"📅 {target_date.strftime('%d %b %Y')}")

    lines.append("📋 Court bookings:")
    if court_df.empty:
        lines.append(" - None")
    else:
        for _, r in court_df.iterrows():
            court = int(r["Court"]) if pd.notna(r["Court"]) else ""
            lines.append(f" - Court {court} | {r['Time Slot']}")

    names = sorted([n for n in attendance_df["Player Name"].dropna().tolist() if str(n).strip()])
    lines.append(f"👥 Attendance: {len(names)}")
    for n in names:
        lines.append(f" - {n}")

    total_collection = float(df["Collection"].sum()) if not df.empty else 0.0
    total_expense = float(df["Expense"].sum()) if not df.empty else 0.0
    balance = total_collection - total_expense

    lines.append("")
    lines.append("💰 Finance (All‑time)")
    lines.append(f" Collection: SGD {total_collection:.2f}")
    lines.append(f" Expense: SGD {total_expense:.2f}")
    lines.append(f" Balance: SGD {balance:.2f}")

    return "\n".join(lines)


def send_dashboard_telegram(target_date: datetime.date):
    """Reload latest data and send dashboard-style message to Telegram."""
    df = load_records()
    msg = build_dashboard_message(df, target_date)
    send_telegram_message(msg)


# -----------------------------
# UI STATE (BUTTON NAV)
# -----------------------------
st.title("Squash Buddies @YCK Attendance, Collection & Expenses")

if "page" not in st.session_state:
    st.session_state.page = "player"

# Top buttons
c1, c2, c3, c4, c5 = st.columns([1, 1.2, 1, 1.2, 1.2])

with c1:
    if st.button("👤 Player"):
        st.session_state.page = "player"
with c2:
    if st.button("💰 Mark Payment"):
        st.session_state.page = "payment"
with c3:
    if st.button("📉 Expense"):
        st.session_state.page = "expense"
with c4:
    if st.button("❌ Remove Booking"):
        st.session_state.page = "remove"
with c5:
    if st.button("🔄 Refresh"):
        # Clear cache and rerun so dashboard reflects manual Google Sheet edits
        st.cache_data.clear()
        bust_cache()
        st.rerun()

st.divider()

# Shared data
next_sundays = get_next_sundays(6)
default_sunday = next_sundays[0]
df = load_records()  # current cached view


# -----------------------------
# SECTION: PLAYER
# -----------------------------
if st.session_state.page == "player":
    st.subheader("👤 Player Attendance")

    player_name = st.text_input("Enter your name").strip()
    play_date = st.selectbox(
        "Select Sunday date",
        next_sundays,
        index=0,
        format_func=lambda d: d.strftime("%d %b %y")
    )

    # prevent duplicates: same date+player+attendance
    exists = False
    if player_name:
        subset = df[
            (df["Description"].str.lower() == "attendance") &
            (df["Date"] == play_date) &
            (df["Player Name"].str.lower() == player_name.lower())
        ]
        exists = not subset.empty

    if st.button("✅ Save Attendance"):
        if not player_name:
            st.error("Please enter your name.")
        elif exists:
            st.warning("You already signed up for this date.")
        else:
            append_record({
                "Date": play_date,
                "Player Name": player_name,
                "Paid": False,
                "Court": "",
                "Time Slot": DEFAULT_TIME_SLOT,
                "Collection": 0,
                "Expense": 0,
                "Description": "Attendance",
            })
            bust_cache()
            st.success("Saved ✅ Telegram sent.")
            send_dashboard_telegram(play_date)
            st.rerun()


# -----------------------------
# SECTION: MARK PAYMENT
# -----------------------------
elif st.session_state.page == "payment":
    st.subheader("💰 Mark Payment (Organizer)")

    pay_date = st.selectbox(
        "Select Sunday to mark payments for",
        next_sundays,
        index=0,
        format_func=lambda d: d.strftime("%d %b %y")
    )

    unpaid = df[
        (df["Description"].str.lower() == "attendance") &
        (df["Date"] == pay_date) &
        (df["Paid"] == False) &
        (df["Player Name"].str.strip() != "")
    ].copy()

    if unpaid.empty:
        st.info("No unpaid players found for this Sunday.")
    else:
        unpaid["label"] = unpaid.apply(
            lambda r: f"{r['Player Name']} | {r['Date'].strftime('%d %b %y') if pd.notna(r['Date']) else 'No date'}",
            axis=1
        )

        selected = st.multiselect(
            "Select players who have paid",
            unpaid["label"].tolist()
        )

        if st.button("✅ Confirm Payment"):
            if not selected:
                st.warning("Please select at least one player.")
            else:
                marked = unpaid[unpaid["label"].isin(selected)]
                for _, r in marked.iterrows():
                    rownum = int(r["_row"])
                    # Set Paid True, Collection fee, Balance fee (Expense unchanged)
                    update_row_cells(rownum, {
                        "Paid": True,
                        "Collection": DEFAULT_FEE,
                        "Balance": DEFAULT_FEE
                    })

                bust_cache()
                st.success("Payment updated ✅ Telegram sent.")
                send_dashboard_telegram(pay_date)
                st.rerun()


# -----------------------------
# SECTION: EXPENSE
# -----------------------------
elif st.session_state.page == "expense":
    st.subheader("📉 Expense (Organizer)")

    expense_type = st.radio("Expense type", ["Court Booking", "Others"])

    if expense_type == "Court Booking":
        booking_date = st.selectbox(
            "Court booking Sunday",
            next_sundays,
            index=0,
            format_func=lambda d: d.strftime("%d %b %y")
        )
        court_number = st.selectbox("Court number", [1, 2, 3, 4, 5])
        time_slot = st.selectbox("Time slot", ["2–3pm", "2–4pm", "3–4pm", "4–5pm"])
        expense_amount = 12 if time_slot == "2–4pm" else 6

        st.write(f"Expense: SGD {expense_amount}")

        if st.button("✅ Save Court Expense"):
            append_record({
                "Date": booking_date,
                "Player Name": "",
                "Paid": "",
                "Court": court_number,
                "Time Slot": time_slot,
                "Collection": 0,
                "Expense": expense_amount,
                "Description": "Court booking",
            })
            bust_cache()
            st.success("Expense saved ✅ Telegram sent.")
            send_dashboard_telegram(booking_date)
            st.rerun()

    else:
        exp_date = st.date_input("Expense date", value=datetime.date.today())
        exp_amount = st.number_input("Amount (SGD)", min_value=0, step=1)
        exp_desc = st.text_input("Description").strip()

        if st.button("✅ Save Other Expense"):
            if not exp_desc:
                st.error("Please enter a description.")
            else:
                append_record({
                    "Date": exp_date,
                    "Player Name": "",
                    "Paid": "",
                    "Court": "",
                    "Time Slot": "",
                    "Collection": 0,
                    "Expense": exp_amount,
                    "Description": exp_desc,
                })
                bust_cache()
                st.success("Expense saved ✅ Telegram sent.")
                # Telegram uses next Sunday summary (dashboard-style) so group stays informed
                send_dashboard_telegram(default_sunday)
                st.rerun()


# -----------------------------
# SECTION: REMOVE BOOKING
# -----------------------------
elif st.session_state.page == "remove":
    st.subheader("❌ Remove Booking")

    remove_date = st.selectbox(
        "Select Sunday",
        next_sundays,
        index=0,
        format_func=lambda d: d.strftime("%d %b %y")
    )

    attendance = df[
        (df["Description"].str.lower() == "attendance") &
        (df["Date"] == remove_date) &
        (df["Player Name"].str.strip() != "")
    ].copy()

    if attendance.empty:
        st.info("No attendance bookings found for this Sunday.")
    else:
        attendance["label"] = attendance.apply(
            lambda r: f"{r['Player Name']} | {r['Date'].strftime('%d %b %y')}",
            axis=1
        )
        selected = st.multiselect(
            "Select bookings to remove",
            attendance["label"].tolist()
        )

        if st.button("✅ Confirm Remove"):
            if not selected:
                st.warning("Please select at least one booking.")
            else:
                rows = attendance[attendance["label"].isin(selected)]["_row"].tolist()
                delete_sheet_rows(rows)
                bust_cache()
                st.success("Removed ✅ Telegram sent.")
                send_dashboard_telegram(remove_date)
                st.rerun()


# -----------------------------
# DASHBOARD (ALWAYS BOTTOM)
# -----------------------------
st.divider()
st.subheader("📊 Dashboard (Always Visible)")

df = load_records()

dash_date = st.selectbox(
    "Dashboard Sunday",
    next_sundays,
    index=0,
    format_func=lambda d: d.strftime("%d %b %y"),
    key="dashboard_date"
)

# Display summary (same info as Telegram)
sunday_df = df[df["Date"] == dash_date]
attendance_df = sunday_df[sunday_df["Description"].str.lower() == "attendance"]
court_df = sunday_df[sunday_df["Description"].str.lower() == "court booking"]

st.markdown(f"### 📅 {dash_date.strftime('%d %b %Y')}")

st.markdown("### 📋 Court bookings")
if court_df.empty:
    st.write("None")
else:
    for _, r in court_df.iterrows():
        court = int(r["Court"]) if pd.notna(r["Court"]) else ""
        st.write(f"- Court {court} | {r['Time Slot']}")

st.markdown("### 👥 Attendance")
names = sorted([n for n in attendance_df["Player Name"].dropna().tolist() if str(n).strip()])
st.write(f"{len(names)} player(s)")
for n in names:
    st.write(f"- {n}")

st.markdown("### 💰 Finance (All‑time)")
total_collection = float(df["Collection"].sum()) if not df.empty else 0.0
total_expense = float(df["Expense"].sum()) if not df.empty else 0.0
balance = total_collection - total_expense

st.write(f"Collection: SGD {total_collection:.2f}")
st.write(f"Expense: SGD {total_expense:.2f}")
st.write(f"✅ Balance: SGD {balance:.2f}")

with st.expander("Show raw records"):
    st.dataframe(df.drop(columns=["_row"], errors="ignore"), use_container_width=True)






