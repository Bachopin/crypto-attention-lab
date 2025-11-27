from datetime import datetime, timezone

def current_timestamp_ms():
    """获取当前 UTC 时间戳（毫秒）"""
    return int(datetime.now(timezone.utc).timestamp() * 1000)

def timestamp_to_str(ts_ms, fmt="%Y-%m-%d %H:%M:%S"):
    """将毫秒时间戳转换为字符串"""
    return datetime.fromtimestamp(ts_ms / 1000, timezone.utc).strftime(fmt)
