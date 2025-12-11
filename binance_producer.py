import asyncio
import json
import signal
import sys
import ssl
from typing import Optional
import websockets
from aiokafka import AIOKafkaProducer
from config import SYMBOLS, KAFKA_BOOTSTRAP, KAFKA_TOPIC, BINANCE_WS_BASE

streams = [f"{symbol.lower()}@trade" for symbol in SYMBOLS]
WS_URL = f"{BINANCE_WS_BASE}?streams={'/'.join(streams)}"

producer: Optional[AIOKafkaProducer] = None
running = True


def signal_handler():
    global running
    print("\nОстановка продьюсера...")
    running = False


async def send_to_kafka(message: str):
    """Отправляем одно сообщение в Kafka"""
    max_retries = 3
    retry_delay = 1
    
    for attempt in range(max_retries):
        try:
            data = json.loads(message)
            if "data" not in data:
                return

            event = data["data"]
            payload = {
                "symbol": event["s"],
                "price": float(event["p"]),
                "qty": float(event["q"]),
                "timestamp": event["T"],
                "is_buyer_maker": event["m"]
            }

            await producer.send_and_wait(
                topic=KAFKA_TOPIC,
                value=json.dumps(payload).encode("utf-8"),
                key=payload["symbol"].encode("utf-8")
            )
            return
            
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"Ошибка отправки в Kafka (попытка {attempt + 1}/{max_retries}): {e}")
                await asyncio.sleep(retry_delay)
                retry_delay *= 2
            else:
                print(f"Не удалось отправить сообщение после {max_retries} попыток: {e}")


async def binance_listener():
    """Основной цикл подключения к Binance WebSocket"""
    global producer

    producer = AIOKafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP,
        value_serializer=lambda v: v,
        key_serializer=lambda k: k,
        acks=1,
        compression_type="gzip"
    )
    await producer.start()

    print(f"Подключение к Binance: {WS_URL}")
    print(f"Запись в Kafka -> {KAFKA_TOPIC}")
    print(f"Отслеживаемые символы: {', '.join(SYMBOLS)}")
    print("Начинаем стриминг...\n")

    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    while running:
        try:
            async with websockets.connect(
                WS_URL,
                ping_interval=20,
                ping_timeout=60,
                max_size=10_000_000,
                ssl=ssl_context
            ) as ws:
                print("WebSocket подключён к Binance\n")
                while running:
                    try:
                        msg = await asyncio.wait_for(ws.recv(), timeout=30)
                        await send_to_kafka(msg)
                    except asyncio.TimeoutError:
                        await ws.ping()
        except Exception as e:
            if running:
                print(f"Соединение разорвано: {e}. Переподключение через 3 сек...")
                await asyncio.sleep(3)

    await producer.stop()
    print("Продьюсер остановлен.")


def main():
    signal.signal(signal.SIGINT, lambda s, f: signal_handler())
    if sys.platform.startswith("win"):
        signal.signal(signal.SIGTERM, lambda s, f: signal_handler())

    try:
        asyncio.run(binance_listener())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()