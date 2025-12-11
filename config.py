import os

# ====================== SYMBOLS ======================
SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"]

# ====================== KAFKA ======================
KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "localhost:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "raw.trades")
KAFKA_GROUP = os.getenv("KAFKA_GROUP", "candlestick-group-v1")

# ====================== REDIS ======================
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

# ====================== API SERVER ======================
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))

# ====================== BINANCE ======================
BINANCE_WS_BASE = "wss://stream.binance.com:9443/stream"