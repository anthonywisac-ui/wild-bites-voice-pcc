# server.py
import os
import asyncio
from fastapi import FastAPI, Request, HTTPException, Query
from aiohttp import ClientSession
from loguru import logger
from pipecat.transports.whatsapp.client import WhatsAppClient

from bot import run_bot

app = FastAPI()
whatsapp_client = None
ice_servers = [{"urls": ["stun:stun.l.google.com:19302"]}]

@app.on_event("startup")
async def startup_event():
    global whatsapp_client
    whatsapp_client = WhatsAppClient(
        whatsapp_token=os.getenv("WHATSAPP_TOKEN"),
        phone_number_id=os.getenv("WHATSAPP_PHONE_NUMBER_ID"),
        session=ClientSession(),
        ice_servers=ice_servers,
        whatsapp_secret=os.getenv("WHATSAPP_APP_SECRET")
    )
    logger.info("WhatsApp Client is ready.")

@app.on_event("shutdown")
async def shutdown_event():
    if whatsapp_client:
        await whatsapp_client.terminate_all_calls()
        await whatsapp_client.session.close()

@app.get("/whatsapp")
async def whatsapp_verify(
    hub_mode: str = Query(..., alias="hub.mode"),
    hub_challenge: int = Query(..., alias="hub.challenge"),
    hub_verify_token: str = Query(..., alias="hub.verify_token"),
):
    expected_token = os.getenv("WHATSAPP_WEBHOOK_VERIFICATION_TOKEN")
    if hub_mode == "subscribe" and hub_verify_token == expected_token:
        logger.info("Webhook verified successfully!")
        return hub_challenge
    logger.warning("Webhook verification failed.")
    raise HTTPException(status_code=403, detail="Verification token mismatch")

@app.post("/whatsapp")
async def whatsapp_webhook(request: Request):
    if not whatsapp_client:
        raise HTTPException(status_code=500, detail="WhatsApp client not initialized")
    
    try:
        # ✅ CRITICAL FIX: Pass the raw request object, NOT the parsed JSON body
        webrtc_connection = await whatsapp_client.handle_webhook_request(request)
        
        if webrtc_connection:
            logger.info("Call accepted! Starting bot...")
            asyncio.create_task(run_bot(webrtc_connection))
        else:
            logger.info("Webhook event was not a call or was ignored.")
            
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
    
    return {"status": "ok"}