import os
from pathlib import Path
from dotenv import load_dotenv

# 确保 .env 在模块加载时被读取
load_dotenv()

from src.config.attention_channels import SYMBOL_ATTENTION_CONFIG

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent

# ==================================
# 更新调度配置
# ==================================
# 价格更新间隔（秒）- 最小粒度 15min，10分钟更新足够
PRICE_UPDATE_INTERVAL = int(os.getenv("PRICE_UPDATE_INTERVAL", 600))  # 10分钟

# 特征值更新冷却期（秒）- 计算开销较大，1小时一次
FEATURE_UPDATE_COOLDOWN = int(os.getenv("FEATURE_UPDATE_COOLDOWN", 3600))  # 1小时

# Google Trends 更新冷却期（秒）- API 限流严格，12小时一次
GOOGLE_TRENDS_COOLDOWN = int(os.getenv("GOOGLE_TRENDS_COOLDOWN", 43200))  # 12小时

# 增量计算所需的滚动窗口天数（用于 z-score 等计算）
ROLLING_WINDOW_CONTEXT_DAYS = 45  # 保留45天上下文用于30天滚动窗口

# 数据目录
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"

# 确保目录存在
RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)

# 日志目录
LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# 数据库配置
# 默认使用 SQLite，如果环境变量中有 DATABASE_URL 则使用环境变量
# 示例 PostgreSQL: "postgresql://user:password@localhost:5432/dbname"
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DATA_DIR}/crypto_attention.db")
# 新闻数据独立存储（如果未指定，默认使用单独的 SQLite 文件）
NEWS_DATABASE_URL = os.getenv("NEWS_DATABASE_URL", f"sqlite:///{DATA_DIR}/crypto_news.db")

# 默认配置
TRACKED_SYMBOLS = ["ZEC/USDT", "BTC/USDT", "ETH/USDT", "SOL/USDT"]
DEFAULT_SYMBOL = TRACKED_SYMBOLS[0]
DEFAULT_TIMEFRAME = "1d"

# Google Trends keyword helper (used by scripts)
GOOGLE_TRENDS_KEYWORDS = {
	symbol: cfg.google_trends_keywords
	for symbol, cfg in SYMBOL_ATTENTION_CONFIG.items()
}
