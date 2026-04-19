import os
import sys
from dotenv import load_dotenv
from loguru import logger

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import LLMContextAggregatorPair
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.services.deepgram.tts import DeepgramTTSService
from pipecat.services.groq.llm import GroqLLMService
from pipecat.transports.base_transport import TransportParams
from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport

load_dotenv()

logger.remove()
logger.add(sys.stdout, level="INFO")

SYSTEM_PROMPT = """You are Alex, a friendly restaurant voice assistant.
Keep responses under 25 words. Ask one question at a time.
Start by greeting the caller and asking for their order.
"""

async def run_bot(transport: SmallWebRTCTransport):
    logger.info("Starting Wild Bites voice bot")

    stt = DeepgramSTTService(
        api_key=os.getenv("DEEPGRAM_API_KEY"),
        model="nova-2-general",
    )

    llm = GroqLLMService(
        api_key=os.getenv("GROQ_API_KEY"),
        model="llama-3.1-8b-instant",
    )

    tts = DeepgramTTSService(
        api_key=os.getenv("DEEPGRAM_API_KEY"),
        voice="aura-asteria-en",
    )

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    context = LLMContext(messages=messages)
    context_aggregator = LLMContextAggregatorPair(context)

    pipeline = Pipeline([
        transport.input(),
        stt,
        context_aggregator.user(),
        llm,
        tts,
        transport.output(),
        context_aggregator.assistant(),
    ])

    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            allow_interruptions=True,
            enable_metrics=True,
        ),
    )

    runner = PipelineRunner(handle_sigint=False)

    # 🔥 FIX 1: FORCE GREETING (MAIN FIX)
    from pipecat.frames.frames import LLMRunFrame

    logger.info("Forcing bot to speak first...")

    messages.append({
        "role": "system",
        "content": "Greet the caller: Hi! Thanks for calling Wild Bites. What can I get for you?",
    })

    await task.queue_frames([LLMRunFrame()])

    # 🔥 FIX 2: KEEP EVENT (backup)
    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        logger.info("Client connected (event triggered)")

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        logger.info("Caller disconnected")
        await task.cancel()

    await runner.run(task)
    logger.info("Voice bot ended")


async def bot(args):
    logger.info(f"WebRTC connection: {args.webrtc_connection}")

    transport = SmallWebRTCTransport(
        webrtc_connection=args.webrtc_connection,
        params=TransportParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            vad_analyzer=SileroVADAnalyzer(),
        ),
    )

    await run_bot(transport)