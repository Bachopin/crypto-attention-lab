
import sys
from pathlib import Path
from sqlalchemy import text

# Add project root to python path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from src.data.db_storage import get_session
from src.database.models import Symbol

def list_symbols():
    session = get_session()
    try:
        symbols = session.query(Symbol).all()
        print(f"Found {len(symbols)} symbols:")
        for s in symbols:
            print(f"ID: {s.id}, Symbol: {s.symbol}, Name: {s.name}")
    finally:
        session.close()

if __name__ == "__main__":
    list_symbols()
