#!/bin/bash
export QDRANT_API_KEY=<YOUR_QDRANT_API_KEY>
export QDRANT_URL=<YOUR_QDRANT_URL>
export COHERE_API_KEY=<YOUR_COHERE_API_KEY>
export TELEGRAM_API_KEY=<YOUR_TELEGRAM_API_KEY>

echo "Starting telegram server"
cd docker/bot || exit
sudo docker-compose up
echo "Telegram server stopped"