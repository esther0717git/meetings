import datetime
import traceback
from datetime import timedelta
from typing import Optional, List, Dict, Any

import pytz
from googleapiclient.discovery import build
from gptsre_tools.tools.register_tool import ToolRegistry
from langchain.callbacks.manager import (
    CallbackManagerForToolRun,
)
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from shopee_smart_arrange_meeting_bot_tools.common.validate import (
    verify_emails_validity,
)
from shopee_smart_arrange_meeting_bot_tools.common.lib import (
    normalize_time_format,
)
from shopee_smart_arrange_meeting_bot_tools.common.smart import SmartAPI
from shopee_smart_arrange_meeting_bot_tools.common.google import (
    get_sea_google_credentials,
    get_shopee_google_credentials,
)


def determine_for_one_period(
    start: datetime.datetime,
    end: datetime.datetime,
    duration: datetime.timedelta,
    calendar_ids: Dict[str, str],
) -> List[Dict]:
    shopee_service = build(
        "calendar", "v3", credentials=get_shopee_google_credentials()
    )
    sea_service = build("calendar", "v3", credentials=get_sea_google_credentials())

    shopee_body = {
        "timeMin": start.isoformat(),
        "timeMax": end.isoformat(),
        "timeZone": "Asia/Singapore",
        "items": [{"id": k} for (k, v) in calendar_ids.items() if v == "shopee"],
    }

    sea_body = {
        "timeMin": start.isoformat(),
        "timeMax": end.isoformat(),
        "timeZone": "Asia/Singapore",
        "items": [{"id": k} for (k, v) in calendar_ids.items() if v == "sea"],
    }

    shopee_response = shopee_service.freebusy().query(body=shopee_body).execute()
    sea_response = sea_service.freebusy().query(body=sea_body).execute()

    busy_slots = {}

    shopee_calendar_list = list(shopee_response.get("calendars", {}).items())
    sea_calendar_list = list(sea_response.get("calendars", {}).items())
    for email, calendar in shopee_calendar_list + sea_calendar_list:
        if calendar.get("error", None):
            continue

        busy_slots[email] = calendar["busy"]

    # Merge all busy blocks across calendars
    busy_blocks = []
    for cal in calendar_ids:
        busy_blocks.extend(busy_slots[cal])

    def merge_intervals(intervals):
        if not intervals:
            return []
        intervals.sort(key=lambda x: x["start"])
        merged = [intervals[0]]
        for current in intervals[1:]:
            last = merged[-1]
            if current["start"] <= last["end"]:
                last["end"] = max(last["end"], current["end"])
            else:
                merged.append(current)
        return merged

    merged_busy = merge_intervals(
        [
            {
                "start": datetime.datetime.fromisoformat(
                    b["start"].replace("Z", "+00:00")
                ),
                "end": datetime.datetime.fromisoformat(b["end"].replace("Z", "+00:00")),
            }
            for b in busy_blocks
        ]
    )

    # Find all free gaps between busy blocks
    free_slots = []
    current = start
    for block in merged_busy:
        if current < block["start"]:
            free_slots.append({"start": current, "end": block["start"]})
        current = max(current, block["end"])
    if current < end:
        free_slots.append({"start": current, "end": end})

    # Slice each free slot into fixed-size windows of `duration`
    available_windows = []
    for slot in free_slots:
        window_start = slot["start"]
        while window_start + duration <= slot["end"]:
            window_end = window_start + duration
            available_windows.append(
                {"start": window_start.isoformat(), "end": window_end.isoformat()}
            )
            window_start = window_end  # move to next window

    return available_windows


class SuggestParticipantAvailabilityInput(BaseModel):
    search_start_time: str = Field(
        description="date time in format of YYYY-MM-dd HH:MM"
    )
    search_end_time: str = Field(description="date time in format of YYYY-MM-dd HH:MM")
    duration_minutes: int = Field(description="how long the meeting in minutes")
    emails: List[str] = Field(description="list of emails to search for")


@ToolRegistry.register_tool(
    "shopee_smart_arrange_meeting_bot_tools",
    SuggestParticipantAvailabilityInput,
    smart_api=SmartAPI(),
)
class SuggestParticipantAvailability(BaseTool):
    name: str = "suggest_participant_availability"
    description: str = "Given a list of participants and office IDs, return potential meeting time slots where most or all participants are available"

    smart_api: SmartAPI

    def _run(
        self,
        search_start_time,
        search_end_time,
        duration_minutes,
        emails,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> Any:
        err = verify_emails_validity(self.smart_api, emails)
        if err:
            return {
                "error": "could not veify email addresses",
                "details": err,
            }

        shopee_service = build(
            "calendar", "v3", credentials=get_shopee_google_credentials()
        )
        sea_service = build("calendar", "v3", credentials=get_sea_google_credentials())

        try:
            start_time = normalize_time_format(search_start_time)
            end_time = normalize_time_format(search_end_time)
            meeting_min_duration = timedelta(minutes=duration_minutes)

            start_time = start_time.astimezone(pytz.timezone("Asia/Singapore"))
            end_time = end_time.astimezone(pytz.timezone("Asia/Singapore"))
            now = datetime.datetime.now().astimezone(pytz.timezone("Asia/Singapore"))
            now_threshold = now - timedelta(hours=1)

            time_debug_details = {
                "now": now.isoformat(),
                "threshold": now_threshold.isoformat(),
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
            }
            if start_time < now_threshold:
                return {
                    "error": "start_time cannot be in the past",
                    "details": time_debug_details,
                }

            if end_time < start_time:
                return {
                    "error": "end_time cannot be before start_time",
                    "details": time_debug_details,
                }

            # Validate for calendar access
            body = {
                "timeMin": start_time.isoformat(),
                "timeMax": end_time.isoformat(),
                "timeZone": "Asia/Singapore",
                "items": [{"id": x} for x in emails],
            }

            email_to_credential_map = {}
            error_email_set = set()

            shopee_response = shopee_service.freebusy().query(body=body).execute()
            for email, calendar in shopee_response["calendars"].items():
                if calendar.get("errors", None):
                    error_email_set.add(email)
                else:
                    email_to_credential_map[email] = "shopee"

            sea_response = sea_service.freebusy().query(body=body).execute()
            for email, calendar in sea_response["calendars"].items():
                if calendar.get("errors", None):
                    error_email_set.add(email)
                else:
                    email_to_credential_map[email] = "sea"

            error_emails = error_email_set - set(email_to_credential_map.keys())

            if error_emails:
                return {
                    "error": "Could not access the calendar of the following emails",
                    "emails": list(error_emails),
                }

            work_days = generate_work_blocks(start_time, end_time)

            results = []
            attendees = []
            attendees.extend([{"email": x} for x in emails])

            for work_day in work_days:
                periods = split_working_hours(work_day[0], work_day[1])
                for p in periods:
                    st, et, lunch_hours = p[0], p[1], p[2]

                    available_slots = [
                        {**x, **{"lunch_hours": lunch_hours, "attendees": attendees}}
                        for x in determine_for_one_period(
                            st,
                            et,
                            meeting_min_duration,
                            email_to_credential_map,
                        )
                    ]

                    results.extend(available_slots)

                # early return
                if len(results) > 10:
                    results = results[:10]
                    break

            return results
        except Exception:
            return str(traceback.format_exc())


def generate_work_blocks(start, end):
    assert start.tzinfo is not None and end.tzinfo is not None, (
        "Use timezone-aware datetimes"
    )

    WORK_START = datetime.time(9, 0)
    WORK_END = datetime.time(18, 30)

    current_day = start.date()
    end_day = end.date()
    tz = start.tzinfo
    results = []

    while current_day <= end_day:
        # Skip Saturday (5) and Sunday (6)
        if current_day.weekday() < 5:
            day_start = datetime.datetime.combine(current_day, WORK_START, tz)
            day_end = datetime.datetime.combine(current_day, WORK_END, tz)

            # Clamp block to the provided start/end range
            block_start = max(start, day_start)
            block_end = min(end, day_end)

            if block_start < block_end:
                results.append((block_start, block_end))

        current_day += datetime.timedelta(days=1)

    return results


def split_working_hours(start, end):
    assert start.tzinfo is not None and end.tzinfo is not None, (
        "Use timezone-aware datetimes"
    )

    WORK_START = datetime.time(9, 30)
    LUNCH_START = datetime.time(12, 0)
    LUNCH_END = datetime.time(14, 0)
    WORK_END = datetime.time(18, 30)

    current = start
    results = []

    while current < end:
        day = current.date()
        tz = current.tzinfo

        # Define periods: (start, end, is_lunch_break)
        day_blocks = [
            (
                datetime.datetime.combine(day, WORK_START, tz),
                datetime.datetime.combine(day, LUNCH_START, tz),
                False,
            ),
            (
                datetime.datetime.combine(day, LUNCH_START, tz),
                datetime.datetime.combine(day, LUNCH_END, tz),
                True,
            ),
            (
                datetime.datetime.combine(day, LUNCH_END, tz),
                datetime.datetime.combine(day, WORK_END, tz),
                False,
            ),
        ]

        for block_start, block_end, is_lunch in day_blocks:
            slot_start = max(current, block_start)
            slot_end = min(end, block_end)
            if slot_start < slot_end:
                results.append((slot_start, slot_end, is_lunch))

        current = datetime.datetime.combine(
            day + datetime.timedelta(days=1), WORK_START, tz
        )

    return results
