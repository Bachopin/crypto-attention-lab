
"""[已弃用] 此脚本已不再需要

之前用于同步 is_active 与 auto_update_price 状态，
但现在系统直接使用 auto_update_price 字段判断代币是否活跃，
不再需要维护两个状态字段。

如果需要清理数据，可以手动运行一次后删除此脚本。
"""
import sys
import warnings
from pathlib import Path

# Add project root to python path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from src.data.db_storage import get_session
from src.database.models import Symbol

warnings.warn(
    "sync_symbol_status.py 已弃用，系统现在直接使用 auto_update_price 字段",
    DeprecationWarning
)

def sync_symbol_status():
    session = get_session()
    try:
        # Find symbols where auto_update_price is False but is_active is True
        symbols = session.query(Symbol).filter(Symbol.auto_update_price == False, Symbol.is_active == True).all()
        
        print(f"Found {len(symbols)} symbols to deactivate:")
        for s in symbols:
            print(f"Deactivating {s.symbol}...")
            s.is_active = False
        
        session.commit()
        print("Sync complete.")
    except Exception as e:
        session.rollback()
        print(f"Error: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    sync_symbol_status()
