from sqlalchemy.orm import Session
from .models import Product

class ProductRepository:
    def __init__(self, db: Session):
        self.db = db

    def find(self, product_id):
        return self.db.query(Product).get(product_id)

    def search(self, **filters):
        query = self.db.query(Product)
        for field, value in filters.items():
            query = query.filter(getattr(Product, field) == value)
        return query.all()
