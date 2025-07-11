from typing import Optional, List, Any

from gptsre_tools.tools.register_tool import ToolRegistry
from langchain.callbacks.manager import (
    CallbackManagerForToolRun,
)
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from shopee_smart_arrange_meeting_bot_tools.common.get_offices import (
    get_office_info_map,
)
from shopee_smart_arrange_meeting_bot_tools.common.smart import SmartAPI


class GetRelevantOfficesInput(BaseModel):
    emails: List[str] = Field(description="list of emails to search for")


@ToolRegistry.register_tool(
    "shopee_smart_arrange_meeting_bot_tools",
    GetRelevantOfficesInput,
    smart_api=SmartAPI(),
)
class GetRelevantOffices(BaseTool):
    name: str = "get_relevant_offices"
    description: str = "Given a list of participants, return the distinct offices they are associated with. Useful for determining which locations should be considered for scheduling."

    smart_api: SmartAPI

    def _run(
        self,
        emails,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> Any:
        resp = []
        office_info_map = get_office_info_map()

        for email in set(emails):
            staff_info_resp = self.smart_api.get_hris_staff_basic_info(email)
            if staff_info_resp.error:
                resp.append(
                    {
                        "email": email,
                        "error": staff_info_resp.error,
                    }
                )
                continue

            staff_info = staff_info_resp.data
            resp.append(
                {
                    "email": email,
                    "office": office_info_map[staff_info.office[0].itemCode],
                }
            )

        return resp
