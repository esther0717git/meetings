#!/usr/bin/env python3
"""
Smart Room Booking Bot: Conflict Resolution & Negotiation

When you request a room for N people at a given time, this script will:
  1. Check if the requested room is free.
  2. If it’s booked by fewer people, prompt you to negotiate with them.
  3. Otherwise, suggest the next free 30-minute slot (up to 4 hours ahead).
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional
import argparse
import sys

@dataclass
class Room:
    id: str
    capacity: int

@dataclass
class Booking:
    room: Room
    start: datetime
    end: datetime
    attendees: int
    user: str

def overlaps(a: Booking, b: Booking) -> bool:
    """Return True if bookings a and b overlap in time."""
    return not (a.end <= b.start or a.start >= b.end)

def find_conflicting_booking(req: Booking, existing: List[Booking]) -> Optional[Booking]:
    """Return the first booking in the same room that overlaps with req, or None."""
    for b in existing:
        if b.room.id == req.room.id and overlaps(req, b):
            return b
    return None

def suggest_for_request(room: Room,
                        num_people: int,
                        start: datetime,
                        duration: timedelta,
                        existing: List[Booking]) -> str:
    """
    Core logic: for your request, either confirm, negotiate, suggest fallback, or apologize.
    """
    req = Booking(room, start, start + duration, num_people, user="you")

    # 1) Room is free: confirm immediately
    conflict = find_conflicting_booking(req, existing)
    if not conflict:
        return (f"{room.id} is free for {num_people} people at "
                f"{start.strftime('%-I:%M %p')}. Booking confirmed!")

    # 2) Room is booked by fewer people: negotiation opportunity
    if conflict.attendees < num_people:
        return (f"{room.id} is booked at {start.strftime('%-I:%M %p')} by "
                f"{conflict.user} for only {conflict.attendees} people. "
                f"Would you like me to message them to see if you can share or swap?")

    # 3) Time-fallback within the same room
    for i in range(1, 9):  # up to 4 hours ahead in 30-min steps
        alt_start = start + timedelta(minutes=30 * i)
        alt_end   = alt_start + duration
        alt_req   = Booking(room, alt_start, alt_end, num_people, user="you")
        if not find_conflicting_booking(alt_req, existing):
            return (f"No rooms at {start.strftime('%-I:%M %p')}, but {room.id} is free from "
                    f"{alt_start.strftime('%-I:%M')}–{alt_end.strftime('%-I:%M')}. "
                    "Should I book this instead?")

    # 4) No options found
    return (f"Sorry, I couldn’t find any free or negotiable slot in "
            f"{room.id} within the next 4 hours.")

def load_sample_data() -> (List[Room], List[Booking]):
    """
    Stub: in a real system, replace this with a database/API call to fetch:
      - Available rooms (and their capacities)
      - Current bookings
    """
    rooms = [
        Room("Room A", capacity=5),
        Room("Room B", capacity=8),
        Room("Room C", capacity=10),
    ]
    existing = [
        # Example: Alice booked Room A from 14:00 to 15:00 for 2 people
        Booking(rooms[0],
                start=datetime(2025,7,11,14,0),
                end  =datetime(2025,7,11,15,0),
                attendees=2,
                user="alice"),
    ]
    return rooms, existing

def parse_args():
    p = argparse.ArgumentParser(description="Request a meeting room.")
    p.add_argument("--room",  required=True,
                   help="Room ID (e.g. 'Room A')")
    p.add_argument("--people", type=int, required=True,
                   help="Number of attendees")
    p.add_argument("--time",   required=True,
                   help="Start time in 'YYYY-MM-DD HH:MM' (24h)")
    p.add_argument("--duration", type=float, default=1.0,
                   help="Duration in hours (default: 1.0)")
    return p.parse_args()

def main():
    args = parse_args()

    # 1) Load rooms & current bookings (replace with real data source)
    rooms, existing = load_sample_data()

    # 2) Find the requested Room object
    matching = [r for r in rooms if r.id.lower() == args.room.lower()]
    if not matching:
        print(f"Error: Room '{args.room}' not found.", file=sys.stderr)
        sys.exit(1)
    room = matching[0]

    # 3) Parse time & duration
    try:
        start = datetime.strptime(args.time, "%Y-%m-%d %H:%M")
    except ValueError:
        print("Error: time must be in 'YYYY-MM-DD HH:MM' format.", file=sys.stderr)
        sys.exit(1)
    duration = timedelta(hours=args.duration)

    # 4) Compute suggestion
    suggestion = suggest_for_request(room, args.people, start, duration, existing)
    print(suggestion)

if __name__ == "__main__":
    main()
