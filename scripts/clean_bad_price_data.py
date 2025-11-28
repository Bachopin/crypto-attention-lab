
import sys
from pathlib import Path
from sqlalchemy import text
import pandas as pd

# Add project root to python path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from src.data.db_storage import get_session
from src.database.models import Price

def clean_bad_price_data():
    session = get_session()
    try:
        print("Scanning for bad price data (non-aligned timestamps)...")
        
        # Find records where timeframe is '1d' but time is not 00:00:00
        # SQLite specific date function usage might be needed, but let's try filtering in python for safety first
        # or use SQL directly if we are confident.
        
        # Let's fetch all 1d prices and check their timestamps
        prices = session.query(Price).filter_by(timeframe='1d').all()
        
        bad_ids = []
        for p in prices:
            # Check if time is 00:00:00
            if p.datetime.hour != 0 or p.datetime.minute != 0 or p.datetime.second != 0 or p.datetime.microsecond != 0:
                bad_ids.append(p.id)
                # print(f"Found bad record: ID={p.id}, SymbolID={p.symbol_id}, Time={p.datetime}, Close={p.close}")
        
        print(f"Found {len(bad_ids)} bad records for timeframe '1d'.")
        
        if bad_ids:
            print("Deleting bad records...")
            # Delete in chunks to avoid too many parameters error
            chunk_size = 500
            for i in range(0, len(bad_ids), chunk_size):
                chunk = bad_ids[i:i+chunk_size]
                session.query(Price).filter(Price.id.in_(chunk)).delete(synchronize_session=False)
            
            session.commit()
            print("Deletion complete.")
        else:
            print("No bad records found.")

    except Exception as e:
        session.rollback()
        print(f"Error: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    clean_bad_price_data()
