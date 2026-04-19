"""
Wild Bites Voice Ordering Bot — Pipecat Cloud (v1.0 API)
=========================================================
WhatsApp Business Calling API voice bot.
Updated for Pipecat 1.0 universal LLMContext API.
Services: Deepgram (STT+TTS) + Groq (LLM)
"""

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


SYSTEM_PROMPT = """
You are Alex, the friendly voice assistant for Wild Bites Restaurant.
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

RULES:
- Minimum $30 for delivery ($4.99 delivery fee)
- Minimum $10 for pickup
- 8% tax added automatically

PERSONALITY:
- Warm, friendly, upbeat — like a good waiter
- SHORT responses (under 25 words, this is spoken aloud)
- No markdown, emojis, or special formatting
- Ask ONE question at a time

CALL FLOW:
1. Greet: "Hi! Thanks for calling Wild Bites. I'm Alex. What can I get for you?"
2. Take order one item at a time. Confirm briefly.
3. Suggest ONE upsell (e.g., "Want fries or a drink?")
4. Ask: delivery or pickup?
5. If delivery: get address. If pickup: ~25 min.
6. Get caller's name.
7. Payment: cash or card-on-delivery?
8. Repeat order + total + ETA before confirming.
9. End: "Your order is confirmed! You'll get a WhatsApp message shortly. Thanks!"

Do not invent menu items. If off-topic, politely redirect to ordering.
"""


async def run_bot(transport: SmallWebRTCTransport):
    """Main bot pipeline using Pipecat 1.0 universal API."""
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
        # Append a priming system message to make the LLM greet
        messages.append({
            "role": "system",
            "content": "Greet the caller warmly and ask what they'd like to order.",
        })
        # Use the new LLMContextFrame approach
        from pipecat.frames.frames import LLMRunFrame
        await task.queue_frames([LLMRunFrame()])

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        logger.info("Caller disconnected")
        await task.cancel()

    runner = PipelineRunner(handle_sigint=False)
    await runner.run(task)
    logger.info("Voice bot ended")


async def bot(args):
    """Entry point invoked by Pipecat Cloud runner."""
    transport = SmallWebRTCTransport(
        webrtc_connection=args.webrtc_connection,
        params=TransportParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            vad_analyzer=SileroVADAnalyzer(),
        ),
    )
    await run_bot(transport)