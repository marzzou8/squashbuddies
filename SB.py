#!/usr/bin/env python
# coding: utf-8

# In[26]:

import streamlit as st
import pandas as pd
import datetime
import requests
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials

st.write(st.secrets["TELEGRAM_TOKEN"])
st.write(st.secrets["gcp_service_account"]["client_email"])

# Authenticate using secrets.toml
scope = ["https://spreadsheets.google.com/feeds",
         "https://www.googleapis.com/auth/drive"]

creds = ServiceAccountCredentials.from_json_keyfile_dict(
    st.secrets["gcp_service_account"], scope
)
client = gspread.authorize(creds)

# Open your sheet (replace with your sheet name)
sheet = client.open("SquashBuddies").sheet1

# Load secrets from .streamlit/secrets.toml
TELEGRAM_TOKEN = st.secrets["TELEGRAM_TOKEN"]
CHAT_ID = st.secrets["CHAT_ID"]

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message}
    requests.post(url, data=payload)

def build_update_message(next_sunday, court_bookings, attendance_count, player_names):
    # Format the date
    message_lines = []
    message_lines.append(f"**Date:** {next_sunday.strftime('%d %b %y')}")

    # Court bookings
    if not court_bookings.empty:
        for _, row in court_bookings.iterrows():
            message_lines.append(f"📋 **Court:** {int(row['Court'])} | **Time:** {row['Time Slot']} | (Date {pd.to_datetime(row['Date']).strftime('%d %b %Y')})")
    else:
        message_lines.append("No court bookings yet.")
    # Attendance
    message_lines.append(f"👥 **Attendance:** {attendance_count} players")

    # Player names
    if player_names:
        message_lines.append("**Players signed up:**")
        for name in sorted(player_names):
            message_lines.append(f"- {name}")
    else:
        message_lines.append("No players signed up yet.")

    # Join everything into one string
    return "\n".join(message_lines)

def load_records():
    return pd.DataFrame(sheet.get_all_records())

def save_record(record_dict):
    # Ensure order matches your sheet headers
    row = [
        record_dict.get("Date"),
        record_dict.get("Player Name"),
        record_dict.get("Paid"),
        record_dict.get("Court"),
        record_dict.get("Time Slot"),
        record_dict.get("Collection"),
        record_dict.get("Expense"),
        record_dict.get("Balance"),
        record_dict.get("Description"),
    ]
    sheet.append_row(row)

st.title("Squash Buddies @YCK Attendance, Collection & Expenses")

payment_number = "97333133"
excel_file = "SB.xlsx"

# Load all records into a DataFrame
records = pd.DataFrame(sheet.get_all_records())

# Append a new record
new_record = ["2026-02-22", "Joyce", False, None, "2–5pm", 0, 0, 0, "Attendance"]
sheet.append_row(new_record)

# --- Generate next 4 Sundays ---
today = datetime.date.today()
days_until_sunday = (6 - today.weekday()) % 7
first_sunday = today + datetime.timedelta(days=days_until_sunday)
next_sundays = [first_sunday + datetime.timedelta(weeks=i) for i in range(4)]

# --- Player Attendance ---
if option == "Player":
    player_name = st.text_input("Enter your name")
    play_date = st.selectbox(
        "Select Sunday date",
        next_sundays,
        format_func=lambda d: d.strftime("%d %b %y")
    )

    if player_name and st.button("Save Attendance"):
        new_record = {
            "Date": play_date,
            "Player Name": player_name,
            "Paid": False,
            "Court": None,
            "Time Slot": "2–5pm",
            "Collection": 0,
            "Expense": 0,
            "Balance": 0,
            "Description": "Attendance"
        }
        records = pd.concat([records, pd.DataFrame([new_record])], ignore_index=True)
        records.to_excel(excel_file, index=False)
        st.success("✅ See you at court!")
          # Build summary and send Telegram
        next_sunday = first_sunday
        court_bookings = records[records["Description"] == "Court booking"] if not records.empty else pd.DataFrame()
        attendance_count = len(records[records["Description"] == "Attendance"]) if not records.empty else 0
        player_names = records[records["Description"] == "Attendance"]["Player Name"].dropna().tolist() if not records.empty else []
        summary_message = build_update_message(next_sunday, court_bookings, attendance_count, player_names)
        send_telegram_message(summary_message)

# --- MARK PAYMENT ---
elif option == "Mark Payment":
    unpaid_records = records[(records["Paid"] == False)]
    if not unpaid_records.empty:
        selected_indices = st.multiselect(
            "Select players to mark as paid",
            unpaid_records.index,
            format_func=lambda i: f"{unpaid_records.loc[i, 'Player Name']} (Date: {pd.to_datetime(unpaid_records.loc[i, 'Date']).strftime('%d %b %Y')})"
        )

        if st.button("Confirm Payment", key="btn_payment"):
            today = datetime.date.today()
            days_until_sunday = (6 - today.weekday()) % 7
            next_sunday = today + datetime.timedelta(days=days_until_sunday)

            marked_names = []
            for i in selected_indices:
                player_name = unpaid_records.loc[i, "Player Name"]

                # Mark payment
                records.loc[i, ["Paid", "Collection", "Balance"]] = [True, 4, 4]
                marked_names.append(player_name)

                # Auto‑signup for next Sunday
                new_record = {
                    "Date": next_sunday,
                    "Player Name": player_name,
                    "Paid": False,
                    "Court": None,
                    "Time Slot": "2–5pm",
                    "Collection": 0,
                    "Expense": 0,
                    "Balance": 0,
                    "Description": "Attendance"
                }
                records = pd.concat([records, pd.DataFrame([new_record])], ignore_index=True)

            records.to_excel(excel_file, index=False)

            st.success(f"✅ Payment marked and auto‑signup done for: {', '.join(marked_names)}")

            # Build and send summary
            court_bookings = records[records["Description"] == "Court booking"] if not records.empty else pd.DataFrame()
            attendance_count = len(records[records["Description"] == "Attendance"]) if not records.empty else 0
            player_names = records[records["Description"] == "Attendance"]["Player Name"].dropna().tolist() if not records.empty else []

            summary_message = build_update_message(next_sunday, court_bookings, attendance_count, player_names)
            send_telegram_message(summary_message)
    else:
        st.info("No unpaid players found.")
# --- EXPENSE ---
elif option == "Expense":
    expense_type = st.radio("Expense type:", ["Court Booking", "Others"])
    today = datetime.date.today()
    days_until_sunday = (6 - today.weekday()) % 7
    first_sunday = today + datetime.timedelta(days=days_until_sunday)
    next_sundays = [first_sunday + datetime.timedelta(weeks=i) for i in range(4)]

    if expense_type == "Court Booking":
        
        booking_date = st.selectbox(
        "Court booking date",
        next_sundays,
        format_func=lambda d: d.strftime("%d %b %y")
        )
        if booking_date.weekday() != 6:
            st.error("⚠️ Court bookings should be on Sunday.")
        else:
            court_number = st.selectbox("Court number", [1, 2, 3, 4, 5])
            time_slot = st.selectbox("Time slot", ["2–3pm", "2–4pm", "3–4pm", "4–5pm"])
            
            # Dynamic expense based on duration
            if time_slot == "2–4pm":
                expense_amount = 12
            else:
                expense_amount = 6

            st.write(f"Court {court_number} booked on {booking_date} for {time_slot}. Expense: SGD {expense_amount}")
            
            if st.button("Save Court Expense"):
                new_record = {
                    "Date": booking_date,
                    "Player Name": None,
                    "Paid": None,
                    "Court": court_number,
                    "Time Slot": time_slot,
                    "Collection": 0,
                    "Expense": expense_amount,
                    "Balance": -expense_amount,
                    "Description": "Court booking"
                }
                records = pd.concat([records, pd.DataFrame([new_record])], ignore_index=True)
                records.to_excel(excel_file, index=False)
                st.success("✅ Court expense saved to Excel!")
                # Build summary and send Telegram
                next_sunday = first_sunday
                court_bookings = records[records["Description"] == "Court booking"] if not records.empty else pd.DataFrame()
                attendance_count = len(records[records["Description"] == "Attendance"]) if not records.empty else 0
                player_names = records[records["Description"] == "Attendance"]["Player Name"].dropna().tolist() if not records.empty else []
                summary_message = build_update_message(next_sunday, court_bookings, attendance_count, player_names)
                send_telegram_message(summary_message)
    
    else:
        booking_date = st.date_input("Expense date", value=datetime.date.today())
        expense_amount = st.number_input("Enter expense amount (SGD)", min_value=0)
        description = st.text_input("Description of expense")
        
        if st.button("Save Other Expense"):
            new_record = {
                "Date": booking_date,
                "Player Name": None,
                "Paid": None,
                "Court": None,
                "Time Slot": None,
                "Collection": 0,
                "Expense": expense_amount,
                "Balance": -expense_amount,
                "Description": description
            }
            records = pd.concat([records, pd.DataFrame([new_record])], ignore_index=True)
            records.to_excel(excel_file, index=False)
            st.success("✅ Other expense saved to Excel!")
            # Build summary and send Telegram
            next_sunday = first_sunday
            court_bookings = records[records["Description"] == "Court booking"] if not records.empty else pd.DataFrame()
            attendance_count = len(records[records["Description"] == "Attendance"]) if not records.empty else 0
            player_names = records[records["Description"] == "Attendance"]["Player Name"].dropna().tolist() if not records.empty else []
            summary_message = build_update_message(next_sunday, court_bookings, attendance_count, player_names)
            send_telegram_message(summary_message)

# --- REMOVE BOOKING ---
elif option == "Remove Booking":
    st.subheader("Remove Booking")
    booked_players = records[records["Player Name"].notna()]["Player Name"].tolist()
    if booked_players:
        remove_player = st.selectbox("Select player to remove", booked_players)
        if st.button("Confirm Remove"):
            records = records.drop(records[records["Player Name"] == remove_player].index)
            records.to_excel(excel_file, index=False)
            st.success(f"❌ Booking removed for {remove_player}")
            # Build summary and send Telegram
            next_sunday = first_sunday
            court_bookings = records[records["Description"] == "Court booking"] if not records.empty else pd.DataFrame()
            attendance_count = len(records[records["Description"] == "Attendance"]) if not records.empty else 0
            player_names = records[records["Description"] == "Attendance"]["Player Name"].dropna().tolist() if not records.empty else []
            summary_message = build_update_message(next_sunday, court_bookings, attendance_count, player_names)
            send_telegram_message(summary_message)
    else:
        st.info("No bookings found.")
# --- Dashboard ---
st.subheader("📊 Records Overview")
records["Date"] = pd.to_datetime(records["Date"], errors="coerce")
# st.dataframe(records)

# Calculate next Sunday
today = datetime.date.today()
days_until_sunday = (6 - today.weekday()) % 7
next_sunday = today + datetime.timedelta(days=days_until_sunday)

# Filter records for that Sunday
sunday_records = records[records["Date"] == pd.to_datetime(next_sunday)]

# Attendance count and player names
attendance_records = sunday_records[sunday_records["Player Name"].notna()]
attendance_count = attendance_records.shape[0]
player_names = attendance_records["Player Name"].tolist()

# Court bookings summary
court_bookings = sunday_records[sunday_records["Description"] == "Court booking"]

# Display summary
st.write(f"**Date:** {next_sunday.strftime('%d %b %y')}")
if not court_bookings.empty:
    for _, row in court_bookings.iterrows():
        st.write(f" 📋 **Court:** {int(row['Court'])} | **Time:** {row['Time Slot']}")
else:
    st.write("No court bookings yet.")

st.write(f"👥 **Attendance:** {attendance_count} players")

# Show player names if any
if player_names:
    st.write("**Players signed up:**")
    for name in sorted(player_names):
        st.write(f"- {name}")
else:
    st.write("No players signed up yet.")

total_collection = records["Collection"].sum()
total_expense = records["Expense"].sum()
balance = total_collection - total_expense

st.write(f"Total Collection: SGD {total_collection}")
st.write(f"Total Expense: SGD {total_expense}")
st.write(f"💰 Current Balance: SGD {balance}")

# if st.button("🔄 Reset Records", key="btn_reset"):
    # Create a fresh empty DataFrame with the right columns
#    records = pd.DataFrame(columns=[
#        "Date", "Player Name", "Paid", "Court", "Time Slot",
#        "Collection", "Expense", "Balance", "Description"
#    ])
#    records.to_excel(excel_file, index=False)
#    st.success("✅ Records have been reset. The app is now blank.")















