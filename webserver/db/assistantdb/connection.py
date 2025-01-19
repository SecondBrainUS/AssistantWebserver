from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from webserver.config import settings
from webserver.db.assistantdb.model import Base, UserWhitelist

print(settings.ASSISTANTDB_URL)
engine = create_engine(settings.ASSISTANTDB_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(engine)

# Initialize User Whitelist from settings
def init_whitelist():
    whitelist_emails = [email.strip() for email in settings.USER_WHITELIST.split(',')]
    with SessionLocal() as db:
        for email in whitelist_emails:
            if not email:
                continue
            whitelist_entry = UserWhitelist(email=email)
            db.merge(whitelist_entry)
        db.commit()

init_whitelist()

def get_db():
    with SessionLocal() as db:
        yield db

def get_db_session():
    return SessionLocal()
