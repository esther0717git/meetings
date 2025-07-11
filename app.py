import streamlit as st
import datetime
import pytz
from typing import List

# Import the SuggestParticipantAvailability tool and helpers
from shopee_smart_arrange_meeting_bot_tools.tools.suggest_participant_availability import SuggestParticipantAvailability

# Streamlit app
def main():
    st.title("Participant Availability Suggestion Tool")
    st.markdown(
        """
        Enter a time range, meeting duration, and participant emails to find available time slots.
        """
    )

    # User inputs
    start_input = st.text_input(
        "Search Start Time (YYYY-MM-DD HH:MM)",
        value="2025-07-15 09:30"
    )
    end_input = st.text_input(
        "Search End Time (YYYY-MM-DD HH:MM)",
        value="2025-07-15 18:00"
    )
    duration_minutes = st.number_input(
        "Meeting Duration (minutes)", min_value=1, value=30
    )
    emails_input = st.text_area(
        "Participant Emails (comma-separated)",
        value="alice@sea.com, bob@sea.com"
    )

    if st.button("Suggest Availability"):
        try:
            # Parse inputs
            emails = [e.strip() for e in emails_input.split(",") if e.strip()]

            # Instantiate the tool
            tool = SuggestParticipantAvailability()
            # Call the tool's _run method directly
            results = tool._run(
                search_start_time=start_input,
                search_end_time=end_input,
                duration_minutes=int(duration_minutes),
                emails=emails
            )

            if isinstance(results, dict) and results.get("error"):
                st.error(f"Error: {results['error']}\nDetails: {results.get('details')}")
            else:
                # Display results as JSON or table
                st.subheader("Available Slots")
                st.json(results)

        except Exception as e:
            st.error(f"Unexpected error: {e}")

if __name__ == "__main__":
    main()
