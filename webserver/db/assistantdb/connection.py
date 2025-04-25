from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import CreateSchema
from webserver.config import settings
from webserver.db.assistantdb.auth_models import Base, UserWhitelist, AUTH_SCHEMA

print(settings.ASSISTANTDB_URL)
engine = create_engine(settings.ASSISTANTDB_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create all tables without schema creation first
Base.metadata.create_all(engine)

def setup_schemas():
    try:
        with engine.connect() as conn:
            inspector = engine.inspect(engine)
            existing_schemas = inspector.get_schema_names()
            
            # Create auth schema if it doesn't exist and isn't the default
            if AUTH_SCHEMA != 'postgres' and AUTH_SCHEMA not in existing_schemas:
                conn.execute(CreateSchema(AUTH_SCHEMA))
                print(f"Created schema: {AUTH_SCHEMA}")
    except Exception as e:
        print(f"Error setting up database schemas: {e}")

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

# Only run these after app has started
init_whitelist()

def get_db():
    with SessionLocal() as db:
        yield db

def get_db_session():
    return SessionLocal()
