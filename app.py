#!/usr/bin/env python3
"""
Streamlit App: Conflict Resolution & Smart Rebooking

This demo asks for:
  - Room ID
  - Number of attendees
  - Desired date & time
and then:
  1. Checks for an overlapping booking
  2. If underutilized, offers a negotiation prompt
  3. Otherwise suggests the next free 30-min slot (up to 4 hours)
"""
import os
import sys
# Ensure helper modules in /mnt/data or current dir are on the path
sys.path.insert(0, "/mnt/data")
sys.path.insert(0, ".")

import streamlit as st
from datetime import datetime, timedelta
from find_available_rooms import find_available_rooms
from search_room import get_conflicting_booking

# --- Helpers ---
def parse_duration(hours: float) -> timedelta:
    return timedelta(hours=hours)


def suggest_next_slot(room: str, start: datetime, duration: timedelta, pax: int):
    """
    Slide the start time by 30-minute increments up to 4 hours to find a free slot.
    Returns (next_start, next_end) or (None, None).
    """
    for i in range(1, 9):
        alt_start = start + timedelta(minutes=30 * i)
        alt_end = alt_start + duration
        try:
            free_rooms = find_available_rooms(room, alt_start, duration, pax)
        except Exception:
            free_rooms = []
        if room in free_rooms:
            return alt_start, alt_end
    return None, None

# --- Streamlit UI ---
st.set_page_config(page_title="Conflict Resolution Demo", layout="centered")
st.title("Conflict Resolution & Smart Rebooking")

# Input fields
room = st.text_input("Room ID (e.g. Room A)", value="Room A")
pax = st.number_input("Number of attendees", min_value=1, max_value=100, value=5)
date = st.date_input("Date", value=datetime.today().date())
time = st.time_input("Start time", value=datetime.now().time().replace(second=0, microsecond=0))
duration_hr = st.number_input("Duration (hours)", min_value=0.5, max_value=4.0, value=1.0, step=0.5)

duration = parse_duration(duration_hr)

if st.button("Check Conflict & Suggest"):
    start = datetime.combine(date, time)
    # 1) Conflict check
    try:
        conflict = get_conflicting_booking(room, start, duration)
    except Exception:
        conflict = None

    if conflict is None:
        st.success(f"✅ {room} is available at {start.strftime('%H:%M')} for {pax} people.")
    else:
        booked_by = getattr(conflict, 'user', 'someone')
        booked_pax = getattr(conflict, 'attendees', '?')
        # 2) Under-utilized negotiation
        if hasattr(conflict, 'attendees') and conflict.attendees < pax:
            st.warning(
                f"⚠️ {room} is already booked by {booked_by} for {booked_pax} people. "
                "Would you like to negotiate to share or swap?"
            )
        else:
            # 3) Fallback suggestion
            next_start, next_end = suggest_next_slot(room, start, duration, pax)
            if next_start:
                st.info(
                    f"No rooms at {start.strftime('%H:%M')}, but {room} is free from "
                    f"{next_start.strftime('%H:%M')}–{next_end.strftime('%H:%M')}. "
                    "Should I book this instead?"
                )
            else:
                st.error(
                    f"Sorry, no free slot in {room} within 4 hours of {start.strftime('%H:%M')}"
                )
