from typing import Optional
import pandas as pd
from fastapi import HTTPException

def validate_date_param(date_str: Optional[str], param_name: str) -> Optional[pd.Timestamp]:
    """统一的时间参数校验函数"""
    if not date_str:
        return None
    try:
        dt = pd.to_datetime(date_str, utc=True)
        if dt.year < 2009:
            raise ValueError(f"{param_name} {dt} is too early (before 2009)")
        # 允许未来1天以内的误差（考虑到时区差异）
        if dt > pd.Timestamp.now(tz='UTC') + pd.Timedelta(days=1):
            raise ValueError(f"{param_name} {dt} is too far in the future")
        return dt
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid {param_name} format: {str(e)}")
