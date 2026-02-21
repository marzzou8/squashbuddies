#!/usr/bin/env python
# coding: utf-8

# In[26]:

import streamlit as st
import pandas as pd
import datetime
import requests
import gspread
from google.oauth2.service_account import Credentials

# -----------------------------
# CONFIG
# -----------------------------
SPREADSHEET_ID = "15RMyE21x8OmcJ35_lqNEanSVuygB3Khpk2r83BiJ654"
DEFAULT_TIME_SLOT = "2–5pm"
DEFAULT_FEE = 4  # collection amount when marking paid

EXPECTED_COLUMNS = [
    "Date", "Player Name", "Paid", "Court", "Time Slot",
    "Collection", "Expense", "Balance", "Description"
]

# -----------------------------
# SECRETS
# -----------------------------
TELEGRAM_TOKEN = st.secrets["TELEGRAM_TOKEN"]
CHAT_ID = st.secrets["CHAT_ID"]

# -----------------------------
# GOOGLE SHEETS AUTH
# -----------------------------
scopes = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
creds = Credentials.from_service_account_info(
    st.secrets["gcp_service_account"],
    scopes=scopes
)
client = gspread.authorize(creds)

# Open the spreadsheet + first worksheet
sheet = client.open_by_key(SPREADSHEET_ID).sheet1


# -----------------------------
# HELPERS
# -----------------------------
def send_telegram_message(message: str):
    """Send plain text Telegram message (no Markdown to avoid formatting issues)."""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message}
    try:
        requests.post(url, data=payload, timeout=10)
    except Exception:
        # Don't crash app if Telegram fails
        pass


def get_next_sundays(n=4):
    today = datetime.date.today()
    days_until_sunday = (6 - today.weekday()) % 7
    first_sunday = today + datetime.timedelta(days=days_until_sunday)
    return [first_sunday + datetime.timedelta(weeks=i) for i in range(n)]


def ensure_sheet_headers():
    """
    Ensure the Google Sheet has the expected header row.
    If the sheet is empty OR header row mismatches, we rewrite headers (and keep existing rows if possible).
    """
    header = sheet.row_values(1)

    # If totally empty, insert headers
    if not header:
        sheet.insert_row(EXPECTED_COLUMNS, 1)
        return

    # Normalize header (strip spaces)
    normalized = [h.strip() for h in header]
    if normalized != EXPECTED_COLUMNS:
        # Best effort: If mismatch, rewrite header row only (do NOT clear data).
        # This prevents KeyErrors. If your data columns are different, fix sheet manually.
        sheet.delete_rows(1)
        sheet.insert_row(EXPECTED_COLUMNS, 1)


@st.cache_data(ttl=15, show_spinner=False)
def load_records_cached(_cache_bust: int = 0):
    """
    Load records from sheet into a DataFrame with a stable schema.
    Adds '_row' column = actual sheet row number (for updates/deletes).
    """
    ensure_sheet_headers()

    values = sheet.get_all_values()
    if len(values) <= 1:
        # only headers or empty
        df = pd.DataFrame(columns=EXPECTED_COLUMNS)
        df["_row"] = pd.Series(dtype=int)
        return df

    headers = [h.strip() for h in values[0]]
    rows = values[1:]

    df = pd.DataFrame(rows, columns=headers)

    # Force schema: add missing expected columns
    for col in EXPECTED_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    # Keep only expected columns (in correct order)
    df = df[EXPECTED_COLUMNS]

    # Track sheet row numbers (data starts from row 2)
    df["_row"] = range(2, 2 + len(df))

    # Type cleanup
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce").dt.date

    # Paid might come back as text; normalize to bool
    def to_bool(x):
        if isinstance(x, bool):
            return x
        s = str(x).strip().lower()
        return s in ("true", "yes", "1")

    df["Paid"] = df["Paid"].apply(to_bool)

    # numeric columns
    for c in ["Collection", "Expense", "Balance"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)

    # Court column numeric-ish
    df["Court"] = pd.to_numeric(df["Court"], errors="coerce")

    # Strings
    df["Player Name"] = df["Player Name"].astype(str).replace("nan", "").fillna("")
    df["Time Slot"] = df["Time Slot"].astype(str).replace("nan", "").fillna("")
    df["Description"] = df["Description"].astype(str).replace("nan", "").fillna("")

    return df


def bust_cache():
    # Bump a counter in session state so cached function reloads
    st.session_state["_cache_bust"] = st.session_state.get("_cache_bust", 0) + 1


def load_records():
    return load_records_cached(st.session_state.get("_cache_bust", 0))


def append_record(record):
    """
    Append a record dict to Google Sheet in EXPECTED_COLUMNS order.
    record keys should match EXPECTED_COLUMNS.
    """
    row = []
    for col in EXPECTED_COLUMNS:
        val = record.get(col, "")
        if isinstance(val, (datetime.date, datetime.datetime)):
            val = val.strftime("%Y-%m-%d")
        elif val is None:
            val = ""
        row.append(val)
    sheet.append_row(row, value_input_option="USER_ENTERED")


def update_row_cells(sheet_row: int, updates: dict):
    """
    Update specific columns for a given sheet row (e.g., mark Paid).
    updates: {"Paid": True, "Collection": 4, ...}
    """
    # Map header to column index
    header = [h.strip() for h in sheet.row_values(1)]
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
        sheet.update_cells(cells, value_input_option="USER_ENTERED")


def delete_sheet_rows(row_numbers):
    """Delete multiple rows safely from bottom to top."""
    for r in sorted(row_numbers, reverse=True):
        sheet.delete_rows(r)


def build_update_message(next_sunday, court_bookings_df, attendance_df):
    lines = []
    lines.append(f"Date: {next_sunday.strftime('%d %b %y')}")

    if not court_bookings_df.empty:
        lines.append("Court bookings:")
        for _, r in court_bookings_df.iterrows():
            court = int(r["Court"]) if pd.notna(r["Court"]) else ""
            lines.append(f" - Court {court} | {r['Time Slot']}")
    else:
        lines.append("No court bookings yet.")

    lines.append(f"Attendance: {len(attendance_df)} player(s)")

    names = sorted([n for n in attendance_df["Player Name"].tolist() if str(n).strip()])
    if names:
        lines.append("Players signed up:")
        for n in names:
            lines.append(f" - {n}")
    else:
        lines.append("No players signed up yet.")

    return "\n".join(lines)


# -----------------------------
# UI
# -----------------------------
# Load data
records = load_records()

st.title("Squash Buddies @YCK Attendance, Collection & Expenses")

# ---- Simple page state ----
if "page" not in st.session_state:
    st.session_state.page = "player"

# ---- Action buttons ----
col1, col2, col3, col4 = st.columns(4)

with col1:
    if st.button("👤 Player"):
        st.session_state.page = "player"

with col2:
    if st.button("❌ Remove Booking"):
        st.session_state.page = "remove"

with col3:
   if st.button("💰 Mark Payment"):
        st.session_state.page = "payment"

with col4:
    if st.button("📉 Expense"):
        st.session_state.page = "expense"

st.divider()

next_sundays = get_next_sundays(4)
next_sunday = next_sundays[0]


# -----------------------------
# TAB: PLAYER
# -----------------------------
if st.session_state.page == "player":
    st.subheader("👤 Player Attendance")

    player_name = st.text_input("Enter your name").strip()
    play_date = st.selectbox(
        "Select Sunday date",
        next_sundays,
        format_func=lambda d: d.strftime("%d %b %y")
    )

    if st.button("Save Attendance"):
        if not player_name:
            st.error("Please enter your name.")
        else:
            append_record({
                "Date": play_date,
                "Player Name": player_name,
                "Paid": False,
                "Court": "",
                "Time Slot": DEFAULT_TIME_SLOT,
                "Collection": 0,
                "Expense": 0,
                "Balance": 0,
                "Description": "Attendance"
            })
            bust_cache()
            st.success("✅ See you at court!")
# -----------------------------
# TAB: MARK PAYMENT
# -----------------------------
elif st.session_state.page == "payment":
    st.subheader("💰 Mark Payment")

    df = load_records()

    unpaid = df[
        (df["Description"].str.lower().str.strip() == "attendance") &
        (df["Paid"] == False) &
        (df["Player Name"].str.strip() != "")
    ].copy()

    if unpaid.empty:
        st.info("No unpaid players.")
    else:
        unpaid["label"] = unpaid.apply(
            lambda r: f"{r['Player Name']} | {r['Date'].strftime('%d %b %y')}",
            axis=1
        )

        selected = st.multiselect(
            "Select players who have paid",
            unpaid["label"].tolist()
        )

        if st.button("Confirm Payment"):
            for _, r in unpaid[unpaid["label"].isin(selected)].iterrows():
                update_row_cells(
                    int(r["_row"]),
                    {
                        "Paid": True,
                        "Collection": DEFAULT_FEE,
                        "Balance": DEFAULT_FEE
                    }
                )

            bust_cache()
            st.success("✅ Payment updated")

# -----------------------------
# TAB: EXPENSE
# -----------------------------
elif st.session_state.page == "expense":
    st.subheader("📉 Expense")

    expense_type = st.radio("Expense type", ["Court Booking", "Others"])

    if expense_type == "Court Booking":
        booking_date = st.selectbox(
            "Booking date",
            next_sundays,
            format_func=lambda d: d.strftime("%d %b %y")
        )
        court_number = st.selectbox("Court", [1, 2, 3, 4, 5])
        time_slot = st.selectbox("Time slot", ["2–3pm", "2–4pm", "3–4pm", "4–5pm"])
        expense_amount = 12 if time_slot == "2–4pm" else 6

        if st.button("Save Court Expense"):
            append_record({
                "Date": booking_date,
                "Player Name": "",
                "Paid": "",
                "Court": court_number,
                "Time Slot": time_slot,
                "Collection": 0,
                "Expense": expense_amount,
                "Balance": -expense_amount,
                "Description": "Court booking"
            })
            bust_cache()
            st.success("✅ Court expense saved")

    else:
        expense_date = st.date_input("Expense date")
        expense_amount = st.number_input("Amount", min_value=0)
        description = st.text_input("Description")

        if st.button("Save Expense"):
            append_record({
                "Date": expense_date,
                "Player Name": "",
                "Paid": "",
                "Court": "",
                "Time Slot": "",
                "Collection": 0,
                "Expense": expense_amount,
                "Balance": -expense_amount,
                "Description": description
            })
            bust_cache()
            st.success("✅ Expense saved")
# -----------------------------
# TAB: REMOVE BOOKING
# -----------------------------
elif st.session_state.page == "remove":
    st.subheader("❌ Remove Booking")

    df = load_records()

    remove_date = st.selectbox(
        "Select Sunday",
        next_sundays,
        format_func=lambda d: d.strftime("%d %b %y")
    )

    attendance = df[
        (df["Description"].str.lower().str.strip() == "attendance") &
        (df["Date"] == remove_date)
    ].copy()

    if attendance.empty:
        st.info("No bookings found.")
    else:
        attendance["label"] = attendance.apply(
            lambda r: f"{r['Player Name']} | {r['Date'].strftime('%d %b %y')}",
            axis=1
        )

        selected = st.multiselect(
            "Select bookings to remove",
            attendance["label"].tolist()
        )

        if st.button("Confirm Remove"):
            rows = attendance[attendance["label"].isin(selected)]["_row"].tolist()
            delete_sheet_rows(rows)
            bust_cache()
            st.success("❌ Booking(s) removed")
# -----------------------------
# TAB: DASHBOARD
# -----------------------------
st.divider()
st.subheader("📊 Dashboard")

# ✅ ALWAYS reload fresh data here
df = load_records()

dashboard_date = st.selectbox(
    "Dashboard Sunday",
    next_sundays,
    format_func=lambda d: d.strftime("%d %b %y"),
    key="dashboard_date"
)

sunday_df = df[df["Date"] == dashboard_date]

attendance_df = sunday_df[
    sunday_df["Description"].str.lower().str.strip() == "attendance"
]

court_df = sunday_df[
    sunday_df["Description"].str.lower().str.strip() == "court booking"
]

st.write(f"👥 Attendance: {len(attendance_df)}")
for n in sorted(attendance_df["Player Name"].dropna()):
    st.write(f"- {n}")

st.write("📋 Court bookings")
if court_df.empty:
    st.write("No court bookings.")
else:
    for _, r in court_df.iterrows():
        st.write(f"Court {int(r['Court'])} | {r['Time Slot']}")

total_collection = df["Collection"].sum()
total_expense = df["Expense"].sum()
balance = total_collection - total_expense

st.write(f"💰 Collection: SGD {total_collection}")
st.write(f"📉 Expense: SGD {total_expense}")
st.write(f"✅ Balance: SGD {balance}")











