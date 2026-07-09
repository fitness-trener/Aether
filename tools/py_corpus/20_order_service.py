import logging

logger = logging.getLogger(__name__)

class OrderService:
    def __init__(self, repo):
        self.repo = repo

    def place_order(self, user_id, items):
        total = sum(item["price"] * item["qty"] for item in items)
        if total <= 0:
            raise ValueError("empty order")
        order = self.repo.save({"user": user_id, "total": total})
        logger.info("order placed: %s", order["id"])
        return order
