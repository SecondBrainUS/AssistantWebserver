from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from webserver.config import settings
from webserver.db.assistantdb.model import Base
print(settings.ASSISTANTDB_URL)
engine = create_engine(settings.ASSISTANTDB_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(engine)

def get_db():
    with SessionLocal() as db:
        yield db

def get_db_session():
    return SessionLocal()
