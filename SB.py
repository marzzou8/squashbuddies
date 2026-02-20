#!/usr/bin/env python
# coding: utf-8

# In[24]:


import streamlit as st
import datetime
import pandas as pd
import os

st.title("Squash Buddies @YCK Attendance, Collection & Expenses")

payment_number = "97333133"
excel_file = "SB.xlsx"

# Load existing records if file exists
if os.path.exists(excel_file):
    records = pd.read_excel(excel_file)
else:
    records = pd.DataFrame(columns=["Date", "Player Name", "Paid", "Court", "Time Slot", "Collection", "Expense", "Balance", "Description"])

option = st.radio("Choose an option:", ["Player", "Mark Payment", "Expense"])

# --- PLAYER ATTENDANCE ---
if option == "Player":
    player_name = st.text_input("Enter your name")
    play_date = st.date_input("Select Sunday date", value=datetime.date.today())

    if play_date.weekday() != 6:
        st.error("⚠️ Please select a Sunday date.")
    elif player_name and st.button("Save Attendance"):
        new_record = {
            "Date": play_date,
            "Player Name": player_name,
            "Paid": False,   # initially unpaid
            "Court": None,
            "Time Slot": "2–5pm",
            "Collection": 0,
            "Expense": 0,
            "Balance": 0,
            "Description": "Attendance"
        }
        records = pd.concat([records, pd.DataFrame([new_record])], ignore_index=True)
        records.to_excel(excel_file, index=False)
        st.success("✅ Attendance saved!")

# --- MARK PAYMENT ---
elif option == "Mark Payment":
    # Show all unpaid players across all dates
    unpaid_records = records[(records["Paid"] == False)]
    
    if not unpaid_records.empty:
        # Let organizer pick player + date
        selected_index = st.selectbox(
            "Select player to mark as paid",
            unpaid_records.index,
            format_func=lambda i: f"{unpaid_records.loc[i, 'Player Name']} (Date: {unpaid_records.loc[i, 'Date'].date()})"
        )
        
        if st.button("Confirm Payment"):
            records.loc[selected_index, ["Paid","Collection","Balance"]] = [True, 4, 4]
            records.to_excel(excel_file, index=False)
            st.success(f"✅ Payment marked for {records.loc[selected_index, 'Player Name']} on {records.loc[selected_index, 'Date'].date()}")
    else:
        st.info("No unpaid players found.")
# --- EXPENSE ---
elif option == "Expense":
    expense_type = st.radio("Expense type:", ["Court Booking", "Others"])
    
    if expense_type == "Court Booking":
        booking_date = st.date_input("Court booking date", value=datetime.date.today())
        if booking_date.weekday() != 6:
            st.error("⚠️ Court bookings should be on Sunday.")
        else:
            court_number = st.selectbox("Court number", [1, 2, 3, 4, 5])
            time_slot = st.selectbox(
                "Time slot",
                ["2–3pm", "2–4pm", "3–4pm", "4–5pm"]   # ✅ includes 2–4pm
            )

            # ✅ Dynamic expense based on duration
            if time_slot == "2–4pm":
                expense_amount = 12   # 2 hours → 6 x 2
            else:
                expense_amount = 6    # default 1 hour

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
        st.write(f"🏸 **Court:** {row['Court']} | **Time:** {row['Time Slot']}")
else:
    st.write("No court bookings yet.")

st.write(f"👥 **Attendance:** {attendance_count} players")

# Show player names if any
if player_names:
    st.write("**Players signed up:**")
    for name in player_names:
        st.write(f"- {name}")
else:
    st.write("No players signed up yet.")

total_collection = records["Collection"].sum()
total_expense = records["Expense"].sum()
balance = total_collection - total_expense

st.write(f"Total Collection: SGD {total_collection}")
st.write(f"Total Expense: SGD {total_expense}")
st.write(f"💰 Current Balance: SGD {balance}")


# In[ ]:





# In[ ]:




