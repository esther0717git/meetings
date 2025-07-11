import traceback
from typing import Optional, List, Any

from googleapiclient.discovery import build
from gptsre_tools.tools.register_tool import ToolRegistry
from langchain.callbacks.manager import (
    AsyncCallbackManagerForToolRun,
    CallbackManagerForToolRun,
)
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from shopee_smart_arrange_meeting_bot_tools.common.get_rooms import (
    normalize_room_identifier_to_room,
)
from shopee_smart_arrange_meeting_bot_tools.common.lib import normalize_time_format
from shopee_smart_arrange_meeting_bot_tools.common.smart import SmartAPI
from shopee_smart_arrange_meeting_bot_tools.common.validate import (
    verify_emails_validity,
)
from shopee_smart_arrange_meeting_bot_tools.tools.find_available_rooms import (
    get_available_rooms_in_window,
)
from shopee_smart_arrange_meeting_bot_tools.common.google import (
    get_shopee_google_credentials,
)


class CreateMeetingInput(BaseModel):
    start_time: str = Field(
        title="Meeting start time",
        description="ISO 8601 format with timezone, e.g. '2025-05-01T14:30:00+08:00'",
    )
    end_time: str = Field(
        title="Meeting end time",
        description="ISO 8601 format with timezone, e.g. '2025-05-01T14:30:00+08:00'",
    )
    title: str = Field(description="title of the event", default="")
    description: str = Field(description="description of the event", default="")
    attendees: List[str] = Field(description="email of the attendees")
    optional_attendees: List[str] = Field(
        description="email of optional attendees", default=[]
    )
    room_ids: List[str] = Field(description="room id of the event", default=[])
    create_meeting_without_room: Optional[bool] = Field(
        description="set this field to true if the user agrees to setup a meeting without any room",
        default=False,
    )


@ToolRegistry.register_tool(
    "shopee_smart_arrange_meeting_bot_tools", CreateMeetingInput, smart_api=SmartAPI()
)
class CreateMeeting(BaseTool):
    name: str = "create_meeting"
    description: str = "Create google calendar event"
    smart_api: SmartAPI

    def _run(
        self,
        start_time,
        end_time,
        attendees,
        title="",
        description="",
        room_ids=None,
        create_meeting_without_room=False,
        optional_attendees=None,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> Any:
        service = build("calendar", "v3", credentials=get_shopee_google_credentials())

        if not title:
            return {"error": "title cannot be empty"}

        if not room_ids and not create_meeting_without_room:
            return {
                "error": "cannot schedule a meeting without a room. You can get confirmation from the user and set create_meeting_without_room to true after"
            }

        if optional_attendees is None:
            optional_attendees = []

        if not (attendees + optional_attendees):
            return {"error": "cannot create a meeting with no participants"}

        err = verify_emails_validity(self.smart_api, attendees + optional_attendees)
        if err:
            return {
                "error": "could not verify email addresses",
                "details": err,
            }

        if not room_ids:
            room_ids = []

        if room_ids:
            resolved_rooms, errors = normalize_room_identifier_to_room(room_ids)
            if len(resolved_rooms) != len(room_ids):
                return errors

            room_ids = [x["id"] for x in resolved_rooms]
            request_body = {
                "timeMin": normalize_time_format(start_time).isoformat(),
                "timeMax": normalize_time_format(end_time).isoformat(),
                "items": [{"id": room_id} for room_id in room_ids],
            }

            freebusy_rooms_response = (
                service.freebusy().query(body=request_body).execute()
            )

            errors = []
            for room_id in room_ids:
                subset = {
                    "calendars": {
                        room_id: freebusy_rooms_response["calendars"][room_id]
                    }
                }

                windows = get_available_rooms_in_window(
                    subset["calendars"],
                    normalize_time_format(start_time),
                    normalize_time_format(end_time),
                )

                if len(windows) == 0:
                    errors.append(
                        {
                            "room_id": room_id,
                            "error": "not available for booking",
                        }
                    )

            if errors:
                return errors

        event_attendees = []
        event_attendees.extend([{"email": x} for x in attendees + room_ids])
        event_attendees.extend(
            [{"email": x, "optional": True} for x in optional_attendees]
        )

        try:
            service = build(
                "calendar", "v3", credentials=get_shopee_google_credentials()
            )

            event = {
                "summary": title,
                "description": description,
                "location": "",
                "start": {
                    "dateTime": normalize_time_format(start_time).isoformat(),
                    "timeZone": "Asia/Singapore",
                },
                "end": {
                    "dateTime": normalize_time_format(end_time).isoformat(),
                    "timeZone": "Asia/Singapore",
                },
                "attendees": event_attendees,
                "guestsCanModify": True,
                "reminders": {
                    "useDefault": True,
                },
            }

            # Insert the event into the calendar
            event = service.events().insert(calendarId="primary", body=event).execute()

            return event
        except Exception:
            return str(traceback.format_exc())

    async def _arun(
        self,
        application_name: str,
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> Any:
        """Use the tool asynchronously."""
        raise NotImplementedError("knowledge_base does not support async")
