import os

def get_logger():
    if os.environ.get("ENV") == "production":
        import structlog
        return structlog.get_logger()
    import logging
    return logging.getLogger("dev")
