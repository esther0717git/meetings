import streamlit as st
from datetime import datetime

# Sample list of rooms/locations (replace with real data source)
ROOMS = ["Room A", "Room B", "Room C", "Conference Hall 1", "Conference Hall 2"]

st.set_page_config(page_title="Smart Meeting Room Booking", layout="centered")

def show_booking_modal():
    with st.modal("New Meeting Request"):
        st.header("Book a Meeting Room")
        pax = st.number_input("How many people?", min_value=1, max_value=100, value=5, key="pax")
        location = st.selectbox("Which room/location?", ROOMS, key="location")
        date = st.date_input("Date", value=datetime.today().date(), key="date")
        time = st.time_input("Time", value=datetime.now().time(), key="time")
        if st.button("Submit Booking", key="submit"):
            # Here you could call your booking logic/API
            st.success(f"Requested room '{location}' for {pax} people on {date} at {time}.")
            st.session_state.show_modal = False


def main():
    st.title("🏢 Smart Meeting Room Booking")
    st.write("Click the button below to start a new room booking request.")

    # Initialize session state for modal visibility
    if "show_modal" not in st.session_state:
        st.session_state.show_modal = False

    # Button to trigger modal
    if st.button("Book a Meeting Room"):
        st.session_state.show_modal = True

    # Show modal if triggered
    if st.session_state.show_modal:
        show_booking_modal()


if __name__ == "__main__":
    main()
