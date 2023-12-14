from bot.conversation import Conversation
from bot.models import Message

from blacksheep import Application, WebSocket, ws
import asyncio
import datetime


app = Application()
conversation = Conversation()

async def stream_message(websocket: WebSocket, message: str):
    # Emulate streaming
    chunk_size = 5
    for start in range(0, len(message), chunk_size):
        chunk = message[start:start + chunk_size]
        response = {"message": chunk}
        await websocket.send_json(response)
        await asyncio.sleep(0.1) 

@ws("/time")
async def time_handler(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            current_time = datetime.datetime.now().strftime("%H:%M:%S")
            await ws.send_text(current_time)
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        pass
    finally:
        await ws.close()

@ws("/message")
async def message_handler(ws: WebSocket):
    await ws.accept()
    global stream_state
    try:
        while True:
            message = await ws.receive_text()
            if message == "@#STOP#@":
                conversation.openai_service.flag.set_streaming_interrupt()
            else:
                await conversation.add_user_prompt(message, ws)         

    except asyncio.CancelledError:
        pass
    finally:
        await ws.close()

@ws("/stop")
async def stop_handler(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            await ws.receive_text()  # We are just waiting for any message to trigger stop
            conversation.openai_service.flag.set_streaming_interrupt()
    except asyncio.CancelledError:
        pass
    finally:
        await ws.close()
