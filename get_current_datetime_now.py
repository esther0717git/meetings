import datetime
from typing import Optional, Any

import pytz
from gptsre_tools.tools.register_tool import ToolRegistry
from langchain.callbacks.manager import (
    CallbackManagerForToolRun,
)
from langchain_core.tools import BaseTool
from pydantic import BaseModel


class GetCurrentDateTimeNow(BaseModel):
    pass


@ToolRegistry.register_tool(
    "shopee_smart_arrange_meeting_bot_tools", GetCurrentDateTimeNow
)
class GetCurrentDateTimeNow(BaseTool):
    name: str = "get_current_datetime_now"
    description: str = (
        "Returns structured information about the current date and time in a fixed timezone. "
        "Useful for grounding vague date references like 'next Monday' or 'after lunch'."
    )

    def _run(
        self,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> Any:
        now = datetime.datetime.now(tz=pytz.timezone("Asia/Singapore"))
        return {
            "iso8601": now.isoformat(),  # Full datetime (with tz)
            "date": now.date().isoformat(),  # Just the date (e.g., "2026-06-25")
            "time": now.strftime("%H:%M %p"),  # Current time in HH:MM (e.g., "14:05")
            "timezone": now.tzinfo.zone,  # "Asia/Singapore"
            "day_of_week": now.strftime("%A"),  # e.g. "Thursday"
            "week_of_year": now.isocalendar().week,  # e.g. 26
        }
