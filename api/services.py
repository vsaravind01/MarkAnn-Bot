import asyncio
import logging
import os
import traceback
from uuid import uuid4

from fastapi import APIRouter, WebSocketDisconnect, websockets
from websockets import ConnectionClosed

from api import websocket_manager
from channels import ai_engine, ann_channel
from common_managers import job_manager
from database import vector_db

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/announcements",
    tags=["services"],
)

QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")

db = vector_db.VectorDB(url=QDRANT_URL, api_key=QDRANT_API_KEY)

manager = websocket_manager.ConnectionManager()
j_manager = job_manager.JobManager()


@router.websocket("/bse/join")
async def websocket_endpoint(websocket: websockets.WebSocket):
    """Establishes a WebSocket connection with the client and sends announcements from BSE.

    Args:
    -----
    websocket: websockets.WebSocket
        websockets.WebSocket connection object
    """
    client_id = uuid4()
    await manager.connect(client_id=str(client_id), websocket=websocket)
    logger.info(f"AnnServices - Connection Established - BSE - Client ID: {client_id}")

    channel = ann_channel.BseChannel(
        category="Company Update",
        subcategory="Press Release / Media Release",
        n_items=10,
        frequency=1,
    )
    engine = ai_engine.AIEngine(channel=channel, db=db)
    sent_items = set()

    try:
        while websocket.client_state != websocket.client_state.DISCONNECTED:
            data = channel.fetch()
            data = [item for item in data if item["id"] not in sent_items]
            ids = [item["id"] for item in data]
            for item in db.get_data_by_ids(ids=ids):
                await manager.send_personal_message(item.payload, websocket)
                sent_items.add(item["id"])
                logger.info(
                    f"AnnServices - Message Sent - BSE - Client ID: {client_id} - Point ID: {item['id']}"
                )
            data = [item for item in data if item["id"] not in sent_items]
            for item in data:
                text = channel.get_pdf_text(item["attachment"])
                summary = engine.summarize_text(text)
                item["summary"] = summary
                await manager.send_personal_message(item, websocket)
                sent_items.add(item["id"])
                pt_id = db.insert_data(
                    text, item, collection_name="market_announcements"
                )
                logger.info(
                    f"AnnServices - Message Sent - BSE - Client ID: {client_id} - Point ID: {pt_id}"
                )
                await asyncio.sleep(1)
            await asyncio.sleep(channel.frequency * 60)
    except WebSocketDisconnect as e:
        manager.remove_connection(client_id=str(client_id))
        logger.error(
            f"AnnServices - Connection Closed - BSE - Client ID: {client_id} - WebSocketDisconnect"
        )
        logger.debug(
            f"AnnServices - WebSocketDisconnect - Code: {e.code} - Reason: {e.reason} - Client ID: {client_id}"
        )
    except ConnectionClosed as e:
        manager.remove_connection(client_id=str(client_id))
        logger.error(
            f"AnnServices - Connection Closed - BSE - Client ID: {client_id} - ConnectionClosed"
        )
        logger.debug(
            f"AnnServices - ConnectionClosed - {str(e)} - Client ID: {client_id}"
        )
    except RuntimeError:
        if (
            manager.active_connections.get(str(client_id)).client_state
            != websocket.client_state.DISCONNECTED
        ):
            await manager.disconnect(client_id=str(client_id))
            return
        await manager.remove_connection(client_id=str(client_id))
        logger.error(f"AnnServices - Connection Removed - BSE - Client ID: {client_id}")
        logger.debug(f"AnnServices - RuntimeError - {traceback.format_exc()}")


@router.delete("/disconnect-all")
async def disconnect_all():
    await manager.close_all_connections()
    return {"message": "All connections closed"}


@router.delete("/disconnect/{client_id}")
async def disconnect(client_id: str):
    if client_id not in manager.active_connections:
        return {"message": f"Connection {client_id} not found"}
    await manager.disconnect(client_id=client_id)
    logger.info(f"AnnServices - Connection Closed - BSE - Client ID: {client_id}")
    return {"message": f"Connection {client_id} closed"}
