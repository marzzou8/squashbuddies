{
 "cells": [
  {
   "cell_type": "code",
   "execution_count": 1,
   "id": "c684f191-5cb6-477d-bdda-c5aaf3ac5208",
   "metadata": {},
   "outputs": [
    {
     "name": "stderr",
     "output_type": "stream",
     "text": [
      "2026-02-20 20:11:33.681 \n",
      "  \u001b[33m\u001b[1mWarning:\u001b[0m to view this Streamlit app on a browser, run it with the following\n",
      "  command:\n",
      "\n",
      "    streamlit run C:\\Users\\mariani\\anaconda3\\Lib\\site-packages\\ipykernel_launcher.py [ARGUMENTS]\n",
      "2026-02-20 20:11:33.687 Session state does not function when running a script without `streamlit run`\n"
     ]
    }
   ],
   "source": [
    "import streamlit as st\n",
    "import datetime\n",
    "\n",
    "st.title(\"🏸 Squash Group Attendance & Payments\")\n",
    "\n",
    "# Court cost input\n",
    "court_cost = st.number_input(\"Court Cost (SGD)\", value=20)\n",
    "payment_number = \"97333133\"\n",
    "\n",
    "st.write(f\"PayNow/PayLah to: {payment_number}\")\n",
    "\n",
    "# Player names\n",
    "players = st.text_area(\"Enter player names (comma separated)\").split(\",\")\n",
    "\n",
    "# Paid players\n",
    "paid_players = st.multiselect(\"Who has paid?\", players)\n",
    "\n",
    "# Calculations\n",
    "total_collected = len(paid_players) * 4\n",
    "outstanding = [p for p in players if p and p not in paid_players]\n",
    "\n",
    "# Summary\n",
    "st.subheader(\"Summary\")\n",
    "st.write(f\"Date: {datetime.date.today()}\")\n",
    "st.write(f\"Players attending: {players}\")\n",
    "st.write(f\"Total collected: SGD {total_collected}\")\n",
    "st.write(f\"Court cost: SGD {court_cost}\")\n",
    "st.write(f\"Balance: SGD {total_collected - court_cost}\")\n",
    "st.write(f\"Outstanding payments: {outstanding}\")"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": None,
   "id": "ef1ee03b-6de0-4928-a5e8-731e92815135",
   "metadata": {},
   "outputs": [],
   "source": []
  }
 ],
 "metadata": {
  "kernelspec": {
   "display_name": "Python [conda env:base] *",
   "language": "python",
   "name": "conda-base-py"
  },
  "language_info": {
   "codemirror_mode": {
    "name": "ipython",
    "version": 3
   },
   "file_extension": ".py",
   "mimetype": "text/x-python",
   "name": "python",
   "nbconvert_exporter": "python",
   "pygments_lexer": "ipython3",
   "version": "3.12.7"
  }
 },
 "nbformat": 4,
 "nbformat_minor": 5
}
