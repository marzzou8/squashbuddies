#!/usr/bin/env python
# coding: utf-8

# In[14]:


import streamlit as st
import datetime
import pandas as pd
import os

st.title("🏸 Squash Group Attendance, Collection & Expenses")

payment_number = "97333133"
excel_file = "sb.xlsx"

# Load existing records if file exists
if os.path.exists(excel_file):
    records = pd.read_excel(excel_file)
else:
    records = pd.DataFrame(columns=["Date", "Player Name", "Court", "Time Slot", "Collection", "Expense", "Balance", "Description"])

option = st.radio("Choose an option:", ["Player", "Collection", "Expense"])

# --- PLAYER ---
if option == "Player":
    player_name = st.text_input("Enter your name")
    play_date = st.date_input("Select Sunday date", value=datetime.date.today())
    
    if player_name and st.button("Save Player Record"):
        new_record = {
            "Date": play_date,
            "Player Name": player_name,
            "Court": None,
            "Time Slot": "2–5pm",
            "Collection": 4,
            "Expense": 0,
            "Balance": 4,
            "Description": "Player booking"
        }
        records = pd.concat([records, pd.DataFrame([new_record])], ignore_index=True)
        records.to_excel(excel_file, index=False)
        st.success("✅ Player record saved to Excel!")

# --- COLLECTION ---
elif option == "Collection":
    num_players = st.number_input("Number of players", min_value=1, step=1)
    total_collection = num_players * 4
    st.write(f"Total collected: SGD {total_collection}")
    st.write(f"Each player pays SGD 4 via PayNow/PayLah to {payment_number}")
    
    if st.button("Save Collection Record"):
        new_record = {
            "Date": datetime.date.today(),
            "Player Name": None,
            "Court": None,
            "Time Slot": None,
            "Collection": total_collection,
            "Expense": 0,
            "Balance": total_collection,
            "Description": "Collection"
        }
        records = pd.concat([records, pd.DataFrame([new_record])], ignore_index=True)
        records.to_excel(excel_file, index=False)
        st.success("✅ Collection record saved to Excel!")

# --- EXPENSE ---
elif option == "Expense":
    expense_type = st.radio("Expense type:", ["Court Booking", "Others"])
    
    if expense_type == "Court Booking":
        booking_date = st.date_input("Court booking date", value=datetime.date.today())
        court_number = st.selectbox("Court number", [1, 2, 3, 4, 5])
        time_slot = st.selectbox("Time slot", ["2–3pm", "3–4pm", "4–5pm"])
        expense_amount = 6
        st.write(f"Court {court_number} booked on {booking_date} for {time_slot}. Expense: SGD {expense_amount}")
        
        if st.button("Save Court Expense"):
            new_record = {
                "Date": booking_date,
                "Player Name": None,
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
    
    else:
        booking_date = st.date_input("Expense date", value=datetime.date.today())
        expense_amount = st.number_input("Enter expense amount (SGD)", min_value=0)
        description = st.text_input("Description of expense")
        
        if st.button("Save Other Expense"):
            new_record = {
                "Date": booking_date,
                "Player Name": None,
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

# --- Dashboard ---
st.subheader("📊 Records Overview")
st.dataframe(records)

# Show total balance
total_collection = records["Collection"].sum()
total_expense = records["Expense"].sum()
balance = total_collection - total_expense

st.write(f"Total Collection: SGD {total_collection}")
st.write(f"Total Expense: SGD {total_expense}")
st.write(f"💰 Current Balance: SGD {balance}")


# In[ ]:




