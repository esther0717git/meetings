#!/usr/bin/env python3
"""
Streamlit Smart Meeting Room Booking App

Features:
  - Ask for pax, location, date/time, duration, participants
  - Validate input
  - Check availability via find_available_rooms
  - If no availability, detect conflicts via search_room
    - If underutilized, offer negotiation prompt via smart
  - Book event via create_event
  - Send negotiation message via seatalk
"""
import streamlit as st
from datetime import datetime, timedelta
import config
from generate_token import get_token
from google import GoogleAPI
from get_rooms import get_rooms
from find_available_rooms import find_available_rooms
from search_room import get_conflicting_booking
from create_event import create_event
from validate import validate_request
from smart import format_negotiation_message
from seatalk import send_message

# --- Initialization ---
st.set_page_config(page_title="Smart Meeting Room Booking", layout="centered")
token = get_token()
api = GoogleAPI(token)

# --- Helpers ---
def parse_duration(hours_float: float) -> timedelta:
    return timedelta(hours=hours_float)

# --- UI Modal ---
def show_booking_modal():
    with st.modal("new_booking_modal"):
        st.header("Book a Meeting Room")
        pax = st.number_input("How many people?", min_value=1, max_value=100, value=5)
        rooms = get_rooms(api)
        room = st.selectbox("Choose room/location:", rooms)
        date = st.date_input("Date", value=datetime.now().date())
        time = st.time_input("Start time", value=datetime.now().time().replace(second=0, microsecond=0))
        duration = st.number_input("Duration (hours)", min_value=0.5, max_value=8.0, value=1.0, step=0.5)
        participants = st.text_area("Participants (comma-separated emails)")

        if st.button("Submit Booking"):
            # Combine date/time
            start = datetime.combine(date, time)
            delta = parse_duration(duration)
            # Validate
            valid, msg = validate_request(pax, room, start, delta)
            if not valid:
                st.error(msg)
                return

            # Check availability
            available = find_available_rooms(api, room, start, delta, pax)
            if available:
                # Book
                event = create_event(api, room, start, delta, pax, participants.split(","))
                st.success(f"Booked '{room}' for {pax} people on {start.strftime('%Y-%m-%d %H:%M')}.")
            else:
                # Conflict detection
                conflict = get_conflicting_booking(api, room, start, delta)
                if conflict and conflict.attendees < pax:
                    # Underutilized booking -> negotiation
                    msg = format_negotiation_message(conflict, pax)
                    st.warning(msg)
                    if st.button("Negotiate with them"):
                        send_message(conflict.user, msg)
                        st.info("Negotiation message sent.")
                else:
                    # Fallback suggestion
                    suggestion = None
                    for i in range(1, 9):
                        alt_start = start + timedelta(minutes=30 * i)
                        if find_available_rooms(api, room, alt_start, delta, pax):
                            suggestion = alt_start
                            break
                    if suggestion:
                        st.info(
                            f"No availability at {start.strftime('%H:%M')}, but '{room}' is free at "
                            f"{suggestion.strftime('%H:%M')} for {duration}h."
                        )
                    else:
                        st.error("Sorry, no available slot found in the next 4 hours.")

# --- Main ---
def main():
    st.title("🏢 Smart Meeting Room Booking")
    st.write("Click below to book a meeting room.")
    if "show_modal" not in st.session_state:
        st.session_state.show_modal = False
    if st.button("Book a Meeting Room"):
        st.session_state.show_modal = True
    if st.session_state.show_modal:
        show_booking_modal()

if __name__ == "__main__":
    main()
