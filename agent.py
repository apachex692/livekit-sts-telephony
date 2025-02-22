from __future__ import annotations

import asyncio
import logging
import os
from time import perf_counter

from dotenv import load_dotenv
from livekit import rtc, api
from livekit.agents import (
    AutoSubscribe,
    JobContext,
    JobProcess,
    WorkerOptions,
    cli,
    llm,
)
from livekit.agents.multimodal import MultimodalAgent
from livekit.agents.pipeline import VoicePipelineAgent
from livekit.plugins import deepgram, openai, silero

load_dotenv(dotenv_path=".env.local")

logger = logging.getLogger("outbound-caller")
logger.setLevel(logging.INFO)

outbound_trunk_id = os.getenv("SIP_OUTBOUND_TRUNK_ID")
_default_instructions = """"""


async def entrypoint(ctx: JobContext):
    global _default_instructions, outbound_trunk_id

    logger.info(f"Connecting to Room: {ctx.room.name}")
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    user_identity = "phone_user"
    phone_number = ctx.job.metadata
    logger.info(f"Dialing: {phone_number} | Room: {ctx.room.name}")

    instructions = _default_instructions + """"""

    await ctx.api.sip.create_sip_participant(
        api.CreateSIPParticipantRequest(
            room_name=ctx.room.name,
            sip_trunk_id=outbound_trunk_id,
            sip_call_to=phone_number,
            participant_identity=user_identity,
        )
    )

    participant = await ctx.wait_for_participant(identity=user_identity)
    run_multimodal_agent(ctx, participant, instructions)

    start_time = perf_counter()
    while perf_counter() - start_time < 30:
        call_status = participant.attributes.get("sip.callStatus")
        if call_status == "active":
            logger.info("Status: User Attended")
            return
        elif call_status == "automation":
            pass
        elif participant.disconnect_reason == \
            rtc.DisconnectReason.USER_REJECTED:
            logger.info("Status: User Rejected")
            break
        elif participant.disconnect_reason == \
            rtc.DisconnectReason.USER_UNAVAILABLE:
            logger.info("Status: User Unavailable")
            break
        await asyncio.sleep(0.1)

    logger.info("Session Timeout")
    ctx.shutdown()


class CallActions(llm.FunctionContext):
    def __init__(
        self, api: api.API, participant: rtc.RemoteParticipant, room: rtc.Room
    ):
        super().__init__()

        self.api = api
        self.participant = participant
        self.room = room

    async def hangup(self):
        try:
            await self.api.room.remove_participant(
                api.RoomParticipantIdentity(
                    room=self.room.name,
                    identity=self.participant.identity,
                )
            )
        except Exception as e:
            logger.error(f"Ending Call Failed: {e}")

    @llm.ai_callable()
    async def end_call(self):
        """Called when the user wants to end the call."""
        logger.info(f"Ending Call: {self.participant.identity}")
        await self.hangup()


def run_voice_pipeline_agent(
    ctx: JobContext, participant: rtc.RemoteParticipant, instructions: str
):
    logger.info("Starting: run_voice_pipeline_agent")

    initial_ctx = llm.ChatContext().append(
        role="system",
        text=instructions,
    )

    agent = VoicePipelineAgent(
        vad=ctx.proc.userdata["vad"],
        stt=deepgram.STT(model="nova-2-phonecall"),
        llm=openai.LLM(),
        tts=openai.TTS(),
        chat_ctx=initial_ctx,
        fnc_ctx=CallActions(api=ctx.api, participant=participant, room=ctx.room),
    )

    agent.start(ctx.room, participant)


def run_multimodal_agent(
    ctx: JobContext, participant: rtc.RemoteParticipant, instructions: str
):
    logger.info("Starting: run_multimodal_agent")

    model = openai.realtime.RealtimeModel(
        instructions=instructions,
        modalities=["audio", "text"],
    )
    agent = MultimodalAgent(
        model=model,
        fnc_ctx=CallActions(api=ctx.api, participant=participant, room=ctx.room),
    )
    agent.start(ctx.room, participant)


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


if __name__ == "__main__":
    if not outbound_trunk_id or not outbound_trunk_id.startswith("ST_"):
        raise ValueError(
            "SIP_OUTBOUND_TRUNK_ID is not set. Please follow the guide at "
            "https://docs.livekit.io/agents/quickstarts/outbound-calls/ to "
            "set it up."
        )
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            agent_name="outbound-caller",
            # prewarm_fnc=prewarm,
        )
    )
