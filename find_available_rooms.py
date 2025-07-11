import datetime
import traceback
from typing import Optional, List, Dict, Any

import pytz
from googleapiclient.discovery import build
from gptsre_tools.tools.register_tool import ToolRegistry
from langchain.callbacks.manager import (
    CallbackManagerForToolRun,
)
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from shopee_smart_arrange_meeting_bot_tools.common.get_offices import get_office_infos
from shopee_smart_arrange_meeting_bot_tools.common.get_rooms import (
    get_rooms,
    normalize_room_identifier_to_room,
)
from shopee_smart_arrange_meeting_bot_tools.common.lib import (
    normalize_time_format,
    divide_into_chunk,
)
from shopee_smart_arrange_meeting_bot_tools.common.google import (
    get_shopee_google_credentials,
)
from shopee_smart_arrange_meeting_bot_tools.tools.search_room import (
    SearchRoomInput,
    SearchRoom,
)


class FindAvailableRoomsInput(BaseModel):
    office_code: str = Field(
        description="Office code to search for available meeting rooms. Each code uniquely identifies an office location."
    )

    window_start: str = Field(
        description="Start time to check for room availability in ISO 8601 format and UTC timezone."
    )
    window_end: str = Field(
        description="End time to check for room availability in ISO 8601 format and UTC timezone."
    )

    room_filter: Optional[SearchRoomInput] = Field(
        default=None,
    )


@ToolRegistry.register_tool(
    "shopee_smart_arrange_meeting_bot_tools",
    FindAvailableRoomsInput,
)
class FindAvailableRooms(BaseTool):
    name: str = "find_available_rooms"
    description: str = (
        "Find available meeting rooms by office code and optional filters"
    )

    def _run(
        self,
        office_code: str,
        window_start: str,
        window_end: str,
        room_filter: Optional[SearchRoomInput] = None,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> Any:
        if not office_code:
            return {"error": "office_code cannot be empty"}

        office = [
            x
            for x in get_office_infos()
            if x["id"] == office_code or x["officeShortName"] == office_code
        ]
        if not office:
            return {"error": f"could not resolve {office_code} to an office"}

        office = office[0]

        if not room_filter:
            room_filter = SearchRoomInput()

        room_filter.office_code_exact = office["id"]
        rooms = SearchRoom().run(
            tool_input=room_filter.model_dump(),
        )

        return CheckRoomAvailability().run(
            tool_input=CheckRoomAvailabilityInput(
                room_ids=[x["id"] for x in rooms],
                window_start=window_start,
                window_end=window_end,
            ).model_dump(),
        )


class GetRoomDetailsInput(BaseModel):
    room_ids: List[str] = Field(description="Room ID to check for details to")


@ToolRegistry.register_tool(
    "shopee_smart_arrange_meeting_bot_tools", GetRoomDetailsInput
)
class GetRoomDetails(BaseTool):
    name: str = "get_room_details"
    description: str = "Returns metadata (like name, seating capacity, level, location and building code) for one or more room id"

    def _run(
        self,
        room_ids,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> Any:
        resolved, errors = normalize_room_identifier_to_room(room_ids)
        if errors:
            return errors

        return resolved


class CheckRoomAvailabilityInput(BaseModel):
    room_ids: List[str] = Field(
        description="List of meeting room IDs to check availability for. Each ID uniquely identifies a room."
    )

    window_start: str = Field(
        description="Start time to check for room availability in ISO 8601 format and UTC timezone."
    )
    window_end: str = Field(
        description="End time to check for room availability in ISO 8601 format and UTC timezone."
    )


@ToolRegistry.register_tool(
    "shopee_smart_arrange_meeting_bot_tools", CheckRoomAvailabilityInput
)
class CheckRoomAvailability(BaseTool):
    name: str = "check_room_availability"
    description: str = (
        "Checks availability of specified meeting rooms "
        "on a particular date and time window."
    )

    def _run(
        self,
        room_ids,
        window_start,
        window_end,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> Any:
        if not room_ids:
            return {"error": "room_ids cannot be empty"}

        all_rooms = get_rooms()

        rooms = []
        for room_id in room_ids:
            for room in all_rooms:
                if room["id"] == room_id:
                    rooms.append(room)

        service = build("calendar", "v3", credentials=get_shopee_google_credentials())

        windows = [
            (
                normalize_time_format(window_start).astimezone(
                    pytz.timezone("Asia/Singapore")
                ),
                normalize_time_format(window_end).astimezone(
                    pytz.timezone("Asia/Singapore")
                ),
            )
        ]

        resp = []
        for w in windows:
            resp.append(
                {
                    "start": w[0].isoformat(),
                    "end": w[1].isoformat(),
                    "available_rooms": [],
                }
            )

        try:
            relevant_rooms = rooms
            relevant_rooms_map = dict([(x["id"], x) for x in relevant_rooms])

            for chunk in divide_into_chunk(relevant_rooms, split_at=50):
                request_body = {
                    "timeMin": min(start for start, _ in windows).isoformat(),
                    "timeMax": max(end for _, end in windows).isoformat(),
                    "calendarExpansionMax": 50,  # this is the maximum you can go
                    "items": [{"id": cid["id"]} for cid in chunk],
                }

                freebusy_rooms_response = (
                    service.freebusy().query(body=request_body).execute()
                )

                for idx, window in enumerate(resp):
                    start = normalize_time_format(window["start"])
                    end = normalize_time_format(window["end"])
                    rooms = get_available_rooms_in_window(
                        freebusy_rooms_response["calendars"],
                        start,
                        end,
                    )

                    window["available_rooms"].extend(rooms)
                    window["available_rooms"] = sorted(
                        window["available_rooms"],
                        key=lambda x: relevant_rooms_map[x]["seating_capacity"],
                    )

                do_all_windows_have_available_rooms = all(
                    [x for x in resp if len(x["available_rooms"]) > 0]
                )

                if do_all_windows_have_available_rooms:
                    break

            return resp
        except Exception:
            return str(traceback.format_exc())


def get_available_rooms_in_window(
    freebusy_data: Dict[str, Dict], start: datetime, end: datetime
) -> List[str]:
    available_rooms = []

    for calendar_id, calendar_info in freebusy_data.items():
        busy_periods = calendar_info.get("busy", [])
        is_free = True

        if calendar_info.get("errors"):
            continue

        for busy in busy_periods:
            busy_start = datetime.datetime.fromisoformat(
                busy["start"].replace("Z", "+00:00")
            )
            busy_end = datetime.datetime.fromisoformat(
                busy["end"].replace("Z", "+00:00")
            )

            # Check if there's an overlap
            if not (end <= busy_start or start >= busy_end):
                is_free = False
                break

        if is_free:
            available_rooms.append(calendar_id)

    return available_rooms
