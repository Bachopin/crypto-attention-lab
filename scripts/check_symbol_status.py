
import sys
from pathlib import Path
from sqlalchemy import text

# Add project root to python path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from src.data.db_storage import get_session
from src.database.models import Symbol

def check_symbol_status():
    session = get_session()
    try:
        symbols = session.query(Symbol).all()
        print(f"{'ID':<5} {'Symbol':<10} {'Active':<10} {'AutoUpdate':<10}")
        print("-" * 40)
        for s in symbols:
            print(f"{s.id:<5} {s.symbol:<10} {str(s.is_active):<10} {str(s.auto_update_price):<10}")
    finally:
        session.close()

if __name__ == "__main__":
    check_symbol_status()
