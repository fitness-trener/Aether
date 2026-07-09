import os

class Settings:
    def __init__(self):
        self.debug = os.environ.get("DEBUG", "false") == "true"
        self.db_url = os.environ["DATABASE_URL"]
        self.workers = int(os.environ.get("WORKERS", "4"))

settings = Settings()
