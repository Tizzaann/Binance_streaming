# Binance Real-Time Candlestick Streaming

Система потоковой обработки данных для отображения свечей криптовалют с Binance в реальном времени.

## Архитектура

```
Binance WebSocket → Kafka → Candlestick Builder → Redis → WebSocket API → Frontend
```

### Компоненты:

1. **binance_producer.py** — получает трейды с Binance WebSocket и отправляет в Kafka
2. **candlestick_builder.py** — агрегирует трейды в 1-минутные свечи и сохраняет в Redis
3. **api_server.py** — FastAPI сервер с WebSocket для отправки данных на фронтенд
4. **index.html** — визуализация свечей в реальном времени с использованием Lightweight Charts

## Быстрый старт


1. Запустите инфраструктуру (Kafka, Zookeeper, Redis):
```bash
docker compose up --build
```

2. Откройте браузер:
```
http://localhost:8000
```

## Конфигурация

Все настройки находятся в файле `config.py`:

```python
# Торгуемые пары
SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"]

# Kafka
KAFKA_BOOTSTRAP = "localhost:9092"
KAFKA_TOPIC = "raw.trades"

# Redis
REDIS_HOST = "localhost"
REDIS_PORT = 6379

# API Server
API_HOST = "0.0.0.0"
API_PORT = 8000
```

## Структура проекта

```
.
├── binance_producer.py      # Producer: Binance → Kafka
├── candlestick_builder.py   # Consumer: Kafka → Redis
├── api_server.py             # WebSocket API сервер
├── config.py                 # Централизованная конфигурация
├── docker-compose.yml        # Kafka, Zookeeper, Redis
├── static/
│   └── index.html            # Frontend интерфейс
└── README.md
```

## Примечания

- Свечи агрегируются по серверному времени (UTC)
- История свечей хранится в Redis Sorted Set
- WebSocket отправляет обновления каждую секунду
- SSL-верификация отключена для Binance WebSocket
