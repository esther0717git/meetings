#!/usr/bin/env python3
"""
Streamlit Smart Meeting Room Booking App

Features:
  - Ask for pax, room, date/time, duration, participants
  - Validate input
  - Use helper modules in /mnt/data:
      * get_current_datetime_now
      * get_relevant_offices
      * get_sender_details
      * find_available_rooms
      * get_conflicting_booking
      * suggest_participant_availability
      * room_map
      * create_event
      * seatalk (message negotiation)
      * generate_token, GoogleAPI for auth
"""
import os
import sys

# Ensure helper modules in /mnt/data are importable
sys.path.insert(0, "/mnt/data")

import streamlit as st

# Third-party
# -- no datetime.now directly; use helper for consistency --
from get_current_datetime_now import now as current_time
from get_sender_details import get_organizer_email
from get_relevant_offices import get_offices_for
from suggest_participant_availability import suggest_availability
from find_available_rooms import find_available_rooms
from search_room import get_conflicting_booking
from room_map import map_room_info
from create_event import create_event
from seatalk import send_message
from validate import validate_request
from generate_token import get_token
from google import GoogleAPI

# --- Initialization ---
st.set_page_config(page_title="Smart Meeting Room Booking", layout="centered")

# Initialize API client
try:
    token = get_token()
    api = GoogleAPI(token)
except Exception as e:
    st.error(f"Failed to initialize API client: {e}")
    st.stop()

# --- Helpers ---
def parse_duration(hours_float: float):
    from datetime import timedelta
    return timedelta(hours=hours_float)

# --- Booking Modal ---
def show_booking_modal():
    st.header("Book a Meeting Room")

    # 1) Organizer fetched automatically
    organizer = get_organizer_email()
    st.write("Organizer:", organizer)

    # 2) Participants & offices
    participants_input = st.text_area("Participants (comma-separated emails)")
    participants = [p.strip() for p in participants_input.split(',') if p.strip()]
    offices = get_offices_for(participants)
    st.write("Participants' Offices:", offices)

    # 3) Purpose (optional)
    purpose = st.text_input("Meeting purpose (optional)")

    # 4) Date & time
    now = current_time()
    default_date = now.date()
    default_time = now.time().replace(second=0, microsecond=0)
    date = st.date_input("Date", value=default_date)
    time = st.time_input("Start time", value=default_time)
    duration = st.number_input("Duration (hours)", min_value=0.5, max_value=8.0, value=0.5, step=0.5)

    # 5) Room selection
    # Offer rooms across each office
    if st.button("Find Available Rooms"):
        start = datetime.combine(date, time)
        delta = parse_duration(duration)
        errors = validate_request(len(participants), None, start, delta)
        if errors[0] is False:
            st.error(errors[1])
            return

        availability = suggest_availability(api, participants, date, duration)
        st.write("Suggested time slots (with availability):")
        for slot in availability:
            st.write(slot)

        # Check rooms per office for chosen slot
        chosen_slot = st.selectbox("Choose slot to book:", availability)
        rooms_by_office = {}
        for office in offices:
            rooms = find_available_rooms(api, office, chosen_slot, delta, len(participants))
            rooms_by_office[office] = rooms
        st.write("Rooms per office:", rooms_by_office)

        # Let user pick one room per office
        selected_rooms = []
        for office, rooms in rooms_by_office.items():
            choice = st.selectbox(f"Select room in {office}:", rooms)
            selected_rooms.append(choice)

        if st.button("Confirm Booking"):
            # Create event and directions
            event = create_event(api, organizer, participants, chosen_slot, delta, selected_rooms, purpose)
            st.success(f"Meeting booked on {chosen_slot} in rooms: {selected_rooms}")
            # Directions
            directions = map_room_info(selected_rooms)
            st.write("Directions:", directions)

# --- Main App ---
def main():
    st.title("🏢 Smart Meeting Room Booking")
    show_booking_modal()

if __name__ == "__main__":
    from datetime import datetime
    main()
