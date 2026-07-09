from contextlib import contextmanager
from .session import SessionLocal

@contextmanager
def unit_of_work():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
