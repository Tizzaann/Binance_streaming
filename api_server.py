import asyncio
import json
from typing import Set
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import redis.asyncio as redis
import uvicorn

from config import REDIS_HOST, REDIS_PORT, SYMBOLS, API_HOST, API_PORT

app = FastAPI(title="Binance Real-time Candles")
app.mount("/static", StaticFiles(directory="static"), name="static")

r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
clients: Set[WebSocket] = set()


async def broadcast_candles():
    """Каждую секунду шлём всем клиентам свежие свечи"""
    while True:
        data = {}
        for symbol in SYMBOLS:
            candle = await r.hgetall(f"candle:1m:{symbol}")
            if candle:
                candle["symbol"] = symbol
                for k in ["open", "high", "low", "close", "volume"]:
                    if k in candle:
                        candle[k] = float(candle[k])
                for k in ["start", "end", "updated"]:
                    if k in candle:
                        candle[k] = int(candle[k])
                data[symbol] = candle
        
        if data:
            message = json.dumps({"type": "candles", "data": data})
            
            if clients:
                tasks = []
                for ws in list(clients):
                    tasks.append(send_to_client(ws, message))
                
                await asyncio.gather(*tasks, return_exceptions=True)
        
        await asyncio.sleep(1)


async def send_to_client(ws: WebSocket, message: str):
    """Отправка сообщения одному клиенту с обработкой ошибок"""
    try:
        await ws.send_text(message)
    except (WebSocketDisconnect, RuntimeError):
        clients.discard(ws)
    except Exception as e:
        print(f"Ошибка отправки сообщения клиенту: {e}")
        clients.discard(ws)


@app.on_event("startup")
async def startup_event():
    try:
        await r.ping()
        print(f"Redis подключён ({REDIS_HOST}:{REDIS_PORT})")
    except Exception as e:
        print(f"Не удалось подключиться к Redis: {e}")
    
    print(f"Отслеживаемые символы: {', '.join(SYMBOLS)}")
    asyncio.create_task(broadcast_candles())


@app.get("/", response_class=HTMLResponse)
async def root():
    with open("static/index.html", encoding="utf-8") as f:
        return f.read()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    clients.add(websocket)
    print(f"Новый WebSocket клиент подключён (всего: {len(clients)})")
    
    history = {}
    for symbol in SYMBOLS:
        raw = await r.zrange("candles:1m:history", -100, -1, withscores=False)
        candles = [json.loads(c) for c in raw if json.loads(c)["symbol"] == symbol]
        history[symbol] = candles[-50:]
    if history:
        await websocket.send_json({"type": "history", "data": history})

    try:
        while True:
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=60)
            except asyncio.TimeoutError:
                try:
                    await websocket.send_json({"type": "ping"})
                except:
                    break
    except WebSocketDisconnect:
        pass
    finally:
        clients.discard(websocket)
        print(f"WebSocket клиент отключён (осталось: {len(clients)})")


if __name__ == "__main__":
    print(f"Запуск API сервера на {API_HOST}:{API_PORT}")
    uvicorn.run("api_server:app", host=API_HOST, port=API_PORT, reload=False)