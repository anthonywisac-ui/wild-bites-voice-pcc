# bot.py
import os
import sys
from dotenv import load_dotenv
from loguru import logger

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.llm_response_universal import LLMContextAggregatorPair
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.services.deepgram.tts import DeepgramTTSService
from pipecat.services.groq.llm import GroqLLMService
from pipecat.transports.base_transport import TransportParams
from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport
from pipecat.frames.frames import LLMContextFrame

load_dotenv()
logger.remove()
logger.add(sys.stdout, level="INFO")

SYSTEM_PROMPT = """You are Alex, a friendly restaurant voice assistant.
Keep responses under 25 words. Ask one question at a time.
Start by greeting the caller and asking for their order.
"""

async def run_bot(webrtc_connection):
    logger.info("Starting Wild Bites voice bot")
    
    # Create transport FIRST
    transport = SmallWebRTCTransport(
        webrtc_connection=webrtc_connection,
        params=TransportParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            vad_analyzer=SileroVADAnalyzer(),
        ),
    )
    
    # Create services
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
    
    # Context aggregator
    context_aggregator = LLMContextAggregatorPair()
    
    # Build pipeline
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
    
    # Initial conversation context
    initial_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    await context_aggregator.assistant().set_context(initial_messages)
    
    # Kickstart the bot to speak first
    await task.queue_frames([LLMContextFrame(initial_messages)])
    
    runner = PipelineRunner(handle_sigint=False)
    await runner.run(task)
    
    logger.info("Voice bot ended")