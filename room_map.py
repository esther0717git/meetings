import collections
import traceback
from typing import Optional, List, Annotated, Any

from gptsre_tools.tools.register_tool import ToolRegistry
from langchain.callbacks.manager import (
    CallbackManagerForToolRun,
)
from langchain_core.tools import BaseTool
from langgraph.prebuilt import InjectedState
from pydantic import BaseModel, Field

from shopee_smart_arrange_meeting_bot_tools.common.get_rooms import (
    normalize_room_identifier_to_room,
)
from shopee_smart_arrange_meeting_bot_tools.common.seatalk import (
    get_base64_encoded_image,
    get_seatalk_session,
)


class ShowRoomMapInput(BaseModel):
    smart_seatalk_thread_id: Annotated[
        str, InjectedState("smart_seatalk_thread_id")
    ] = Field(description="Seatalk thread id retrieved from injected state", default="")

    smart_seatalk_group_id: Annotated[str, InjectedState("smart_seatalk_group_id")] = (
        Field(description="Seatalk group id retrieved from injected state", default="")
    )

    room_ids: List[str] = Field(description="room_ids that are scheduled")


@ToolRegistry.register_tool("shopee_smart_arrange_meeting_bot_tools", ShowRoomMapInput)
class ShowRoomMap(BaseTool):
    name: str = "send_room_map_image"
    description: str = "Display a map to the meeting room"

    def _run(
        self,
        smart_seatalk_thread_id="",
        smart_seatalk_group_id="",
        room_ids=None,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> Any:
        seatalk_group_id = smart_seatalk_group_id
        seatalk_thread_id = smart_seatalk_thread_id

        if not room_ids:
            return {"error": "room_ids cannot be empty"}

        rooms, errors = normalize_room_identifier_to_room(room_ids)
        if len(rooms) != len(room_ids):
            return errors

        grouped_by_level = collections.defaultdict(list)
        for room in rooms:
            grouped_by_level[room["level"]].append(room)

        if seatalk_group_id and seatalk_thread_id:
            errors = []
            messages = []

            for level, rooms in grouped_by_level.items():
                if not rooms[0]["direction_image_path"]:
                    errors.append(
                        {
                            "rooms": rooms,
                            "error": "could not find directions to these rooms",
                        }
                    )
                    continue

                room_titles = ",".join([x["title"] for x in rooms])
                room_messages = [
                    {
                        "group_id": seatalk_group_id,
                        "message": {
                            "tag": "text",
                            "text": {
                                "content": f"Here is the direction to {room_titles}",
                            },
                            "thread_id": seatalk_thread_id,
                        },
                    },
                    {
                        "group_id": seatalk_group_id,
                        "message": {
                            "tag": "image",
                            "image": {
                                "content": get_base64_encoded_image(
                                    rooms[0]["direction_image_path"]
                                ),
                            },
                            "thread_id": seatalk_thread_id,
                        },
                    },
                ]

                messages.extend(room_messages)

            try:
                for m in messages:
                    resp = get_seatalk_session().post(
                        "https://openapi.seatalk.io/messaging/v2/group_chat",
                        json=m,
                    )

                    if resp.status_code != 200:
                        raise RuntimeError(resp.status_code, resp.text)

                    if resp.json()["code"] != 0:
                        raise RuntimeError(resp.status_code, resp.text, m)

            except RuntimeError:
                return traceback.format_exc()

            return {
                "channel": "seatalk",
                "errors": errors,
            }

        errors = []
        urls = []
        for level, rooms in grouped_by_level.items():
            if not rooms[0]["direction_image_path"]:
                errors.append(
                    {
                        "rooms": rooms,
                        "error": "could not find directions to these rooms",
                    }
                )
                continue

            urls.append(
                {
                    "rooms": rooms,
                    "image_url": "https://proxy.uss.s3.sz.shopee.io/api/v4/50010503/seer/"
                    + rooms[0]["direction_image_path"].split("/")[-1],
                }
            )

        return {
            "channel": "web",
            "data": urls,
            "errors": errors,
        }
