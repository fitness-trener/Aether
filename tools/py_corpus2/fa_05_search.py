from fastapi import FastAPI, Query
from elasticsearch import Elasticsearch

app = FastAPI()
es = Elasticsearch("http://localhost:9200")

@app.get("/search")
def search(q: str = Query(...)):
    result = es.search(index="docs", query={"match": {"body": q}})
    hits = result["hits"]["hits"]
    return [h["_source"] for h in hits]
