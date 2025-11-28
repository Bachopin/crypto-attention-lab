
import sys
from pathlib import Path
from sqlalchemy import text

# Add project root to python path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from src.data.db_storage import get_session
from src.database.models import Symbol

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
