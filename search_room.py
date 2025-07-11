from typing import Optional, Union, Any

from gptsre_tools.tools.register_tool import ToolRegistry
from langchain.callbacks.manager import (
    CallbackManagerForToolRun,
)
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from shopee_smart_arrange_meeting_bot_tools.common.get_offices import get_office_infos
from shopee_smart_arrange_meeting_bot_tools.common.get_rooms import get_rooms


class SearchRoomInput(BaseModel):
    room_name_contains: Optional[str] = Field(
        description="Partial or full name of the room to search for. For example: 'Hardjonagoro', 'A5F-6'.",
        default="",
    )

    office_code_exact: Optional[str] = Field(
        description="Exact office code to search for. For example: 'WXyj74Gx'",
        default="",
    )

    office_name_contains: Optional[str] = Field(
        description="Partial or full name of the office to search for",
        default="",
    )

    country_contains: Optional[str] = Field(
        description="Partial or full name of the country to search for", default=""
    )

    city_contains: Optional[str] = Field(
        description="Partial or full name of the city to search for", default=""
    )

    level: Optional[Union[int, str]] = Field(
        default=None,
        description="Optional level of the room to filter by. If not provided, all available rooms are considered regardless of level.",
    )

    minimum_capacity: Optional[Union[int, str]] = Field(
        default=1,
        description="Optional minimum number of attendees the room must accommodate. If not provided, all available rooms are considered regardless of size.",
    )


@ToolRegistry.register_tool(
    "shopee_smart_arrange_meeting_bot_tools",
    SearchRoomInput,
)
class SearchRoom(BaseTool):
    name: str = "search_room"
    description: str = "Searches for meeting rooms based on a natural language query, which may include building names, floor levels, or partial room names. Useful for helping users locate rooms before showing directions."

    def _run(
        self,
        room_name_contains="",
        office_name_contains="",
        office_code_exact="",
        country_contains="",
        city_contains="",
        level=None,
        minimum_capacity=1,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> Any:
        if not any(
            [
                room_name_contains,
                office_name_contains,
                office_code_exact,
                country_contains,
                city_contains,
            ]
        ):
            return {"error": "require at least one parameter to search"}

        office_filter = []

        if office_code_exact:
            office_filter.append(lambda x: x["id"] == office_code_exact)

        if office_name_contains:
            office_filter.append(
                lambda x: office_name_contains.lower() in x["name"].lower()
            )

        if country_contains:
            office_filter.append(
                lambda x: country_contains.lower() in x["country"].lower()
            )

        if city_contains:
            office_filter.append(
                lambda x: x["city"] and city_contains.lower() in x["city"].lower()
            )

        offices = [x for x in get_office_infos() if all([y(x) for y in office_filter])]

        # return early since there are office filters, but nothing returned
        if not offices and any(
            [office_code_exact, office_name_contains, country_contains, city_contains]
        ):
            return []

        room_filter = []
        if room_name_contains:
            room_filter.append(
                lambda x: room_name_contains.lower() in x["title"].lower()
            )

        if level:
            room_filter.append(lambda x: x["level"] == int(level))

        if minimum_capacity:
            room_filter.append(lambda x: x["seating_capacity"] >= int(minimum_capacity))

        if offices:
            office_ids = [x["id"] for x in offices]
            room_filter.append(lambda x: x["building_code"] in office_ids)

        rooms = [x for x in get_rooms() if all([y(x) for y in room_filter])]
        return rooms
