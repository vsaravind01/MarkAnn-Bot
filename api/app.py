import logging
from datetime import datetime

from fastapi import FastAPI
from qdrant_client import QdrantClient, models

from api import services

logging.basicConfig(
    level=logging.DEBUG,
    filename=f"./logs/{datetime.today()}-app.log",
    filemode="w",
    format="%(asctime)s - %(name)s - %(message)s",
)

app = FastAPI()
app.include_router(services.router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.on_event("startup")
async def startup_event():
    client = QdrantClient(host="localhost", port=6333)
    if not client.collection_exists("market_announcements"):
        logger.info(
            "collection existence check - market_announcements does not exist. Creating..."
        )
        client.create_collection(
            collection_name="market_announcements",
            vectors_config=models.VectorParams(
                size=1024,
                distance=models.Distance.COSINE,
            ),
        )
        logger.info("create collection - market_announcements created successfully")
    else:
        logger.info("collection existence check - market_announcements exists")
    logger.info("startup event - completed")
    client.close()
