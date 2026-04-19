"""Wild Bites Voice Ordering Bot — Pipecat Cloud."""

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
from pipecat.runner.types import RunnerArguments
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.services.deepgram.tts import DeepgramTTSService
from pipecat.services.groq.llm import GroqLLMService
from pipecat.transports.base_transport import BaseTransport, TransportParams
from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport

load_dotenv()

logger.remove()
logger.add(sys.stdout, level="INFO")


SYSTEM_PROMPT = """You are Alex, the friendly voice assistant for Wild Bites Restaurant.
You take orders over the phone via WhatsApp calling.

MENU (USD):
- BURGERS: Classic Smash $8.99, Bacon Cheeseburger $10.99, Double Smash $12.99, Chicken Sandwich $9.99
- PIZZA: Margherita $13.99, Pepperoni $15.99, BBQ Chicken $16.99, Veggie Supreme $14.99
- BBQ: Half Rack Ribs $18.99, Full Rack Ribs $28.99, Brisket Plate $19.99
- FISH: Grilled Salmon $19.99, Fish & Chips $14.99, Shrimp Platter $17.99
- SIDES: Fries $3.99, Mac & Cheese $4.99, Coleslaw $2.99, 6 Wings $7.99, Nachos $6.99
- DRINKS: Coke $2.49, Pepsi $2.49, Shakes $4.99
- DESSERTS: Brownie $4.99, Chocolate Cake $5.99
- DEALS: Family Bundle $29.99, Duo Deal $18.99

RULES: Min $30 delivery ($4.99 fee). Min $10 pickup. 8% tax added.

PERSONALITY: Warm, friendly, upbeat. SHORT responses (under 25 words, spoken).
No markdown or emojis. Ask ONE question at a time.

CALL FLOW:
1. Greet warmly.
2. Take order. Confirm.
3. Suggest ONE upsell.
4. Delivery or pickup?
5. Address (delivery) / 25 min ETA (pickup).
6. Name.
7. Cash or card-on-delivery?
8. Repeat order + total + ETA.
9. Confirm: "Order confirmed! WhatsApp message coming shortly. Thanks!"

Do not invent menu items. Redirect off-topic to ordering.
"""


async def run_bot(transport: BaseTransport):
    """Bot pipeline logic — transport agnostic."""
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

    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        logger.info("Caller connected — triggering greeting")
        messages.append({
            "role": "system",
            "content": "Greet the caller warmly and ask what they'd like to order.",
        })
        from pipecat.frames.frames import LLMRunFrame
        await task.queue_frames([LLMRunFrame()])

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        logger.info("Caller disconnected")
        await task.cancel()

    runner = PipelineRunner(handle_sigint=False)
    await runner.run(task)


async def bot(runner_args: RunnerArguments):
    """Entry point — Pipecat Cloud calls this."""
    transport = SmallWebRTCTransport(
        webrtc_connection=runner_args.webrtc_connection,
        params=TransportParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            vad_analyzer=SileroVADAnalyzer(),
        ),
    )
    await run_bot(transport)


if __name__ == "__main__":
    from pipecat.runner.run import main
    main()