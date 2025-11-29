from src.data.db_storage import get_db, get_session
from src.database.models import News

def backfill_language():
    db = get_db()
    session = get_session(db.news_engine)
    try:
        # Update all news with missing language to 'en'
        # Since our sources are English-centric for now.
        count = session.query(News).filter(
            (News.language == None) | (News.language == '') | (News.language == 'Unknown')
        ).update({News.language: 'en'}, synchronize_session=False)
        
        session.commit()
        print(f"Updated {count} news items with language='en'")
    except Exception as e:
        print(f"Error: {e}")
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    backfill_language()
