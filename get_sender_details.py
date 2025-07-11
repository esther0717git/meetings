import traceback
from typing import Optional, Annotated, Any

from gptsre_tools.tools.register_tool import ToolRegistry
from langchain.callbacks.manager import (
    CallbackManagerForToolRun,
)
from langchain_core.tools import BaseTool
from langgraph.prebuilt import InjectedState
from pydantic import BaseModel, Field


class GetSenderSeatalkInfoInput(BaseModel):
    smart_user_id: Annotated[Optional[str], InjectedState("smart_user_id")] = Field(
        description="user email injected by platform channel",
        default="unknown",
    )
    smart_seatalk_email: Annotated[
        Optional[str], InjectedState("smart_seatalk_email")
    ] = Field(
        description="employee email injected by seatalk channel",
        default="",
    )
    seatalk_email: Annotated[Optional[str], InjectedState("seatalk_email")] = Field(
        description="employee email injected by seatalk channel",
        default="",
    )


@ToolRegistry.register_tool(
    "shopee_smart_arrange_meeting_bot_tools", GetSenderSeatalkInfoInput
)
class GetSenderDetails(BaseTool):
    name: str = "get_sender_seatalk_info"
    description: str = "Return sender's seatalk details"

    def _run(
        self,
        smart_user_id="",
        smart_seatalk_email="",
        seatalk_email="",
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> Any:
        try:
            if smart_seatalk_email:
                return {"email": smart_seatalk_email}

            if smart_user_id and smart_user_id != "unknown":
                return {"email": smart_user_id}

            if seatalk_email:
                return {"email": seatalk_email}

            return {"error": "could not find user information"}

        except RuntimeError:
            return str(traceback.format_exc())
