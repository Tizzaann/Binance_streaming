# candlestick_builder.py
import asyncio
import json
import os
from collections import defaultdict
from datetime import datetime
import redis.asyncio as redis
from aiokafka import AIOKafkaConsumer
from aiokafka.errors import KafkaConnectionError
from config import (
    KAFKA_BOOTSTRAP, KAFKA_TOPIC, KAFKA_GROUP,
    REDIS_HOST, REDIS_PORT
)

current_candles = defaultdict(lambda: {
    "open": None,
    "high": 0.0,
    "low": float("inf"),
    "close": None,
    "volume": 0.0,
    "trades": 0,
    "start_ts": None
})

r = None


def get_minute_bucket(ts_ms: int) -> int:
    return (ts_ms // 60_000) * 60_000


async def update_candle(symbol: str, price: float, qty: float, ts_ms: int):
    bucket = get_minute_bucket(ts_ms)

    candle = current_candles[f"{symbol}:{bucket}"]

    if candle["open"] is None:
        candle["open"] = price
        candle["start_ts"] = bucket

    candle["high"] = max(candle["high"], price)
    candle["low"] = min(candle["low"], price)
    candle["close"] = price
    candle["volume"] += qty
    candle["trades"] += 1

    final_candle = {
        "symbol": symbol,
        "open": candle["open"],
        "high": candle["high"],
        "low": candle["low"],
        "close": candle["close"],
        "volume": round(candle["volume"], 8),
        "trades": candle["trades"],
        "start": candle["start_ts"],
        "end": candle["start_ts"] + 60_000,
        "ts": int(datetime.now().timestamp() * 1000)
    }

    key = f"candle:1m:{symbol}"
    await r.hset(key, mapping={
        "open": final_candle["open"],
        "high": final_candle["high"],
        "low": final_candle["low"],
        "close": final_candle["close"],
        "volume": final_candle["volume"],
        "trades": final_candle["trades"],
        "updated": final_candle["ts"]
    })

    await r.zadd("candles:1m:history", {json.dumps(final_candle): bucket})


async def process_message(message):
    try:
        data = json.loads(message.value.decode("utf-8"))
        symbol = data["symbol"]
        price = data["price"]
        qty = data["qty"]
        ts = data["timestamp"]

        await update_candle(symbol, price, qty, ts)
    except Exception as e:
        print(f"Ошибка обработки сообщения: {e}")


async def minute_cleaner():
    while True:
        await asyncio.sleep(30)
        now = get_minute_bucket(int(datetime.now().timestamp() * 1000))
        to_delete = [k for k in current_candles if int(k.split(":")[1]) < now - 120_000]
        for k in to_delete:
            del current_candles[k]


async def main():
    global r
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=False)

    consumer = AIOKafkaConsumer(
        KAFKA_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id=KAFKA_GROUP,
        auto_offset_reset="latest",
        enable_auto_commit=True
    )

    try:
        await r.ping()
        print("Redis подключён")
    except:
        print("Не удалось подключиться к Redis!")
        return

    asyncio.create_task(minute_cleaner())

    while True:
        try:
            await consumer.start()
            print(f"Старт потребления из {KAFKA_TOPIC} ...")
            break
        except KafkaConnectionError:
            print("Kafka недоступна, ждём 5 сек...")
            await asyncio.sleep(5)

    try:
        async for msg in consumer:
            await process_message(msg)
    finally:
        await consumer.stop()
        await r.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nОстановка обработчика свечей...")