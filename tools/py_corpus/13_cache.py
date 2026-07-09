class LRUCache:
    def __init__(self, capacity):
        self.capacity = capacity
        self.store = {}
        self.order = []

    def get(self, key):
        if key not in self.store:
            return None
        self.order.remove(key)
        self.order.append(key)
        return self.store[key]

    def put(self, key, value):
        if key in self.store:
            self.order.remove(key)
        elif len(self.store) >= self.capacity:
            oldest = self.order.pop(0)
            del self.store[oldest]
        self.store[key] = value
        self.order.append(key)
