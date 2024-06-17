echo "Starting telegram server"
cd docker/bot || exit
sudo docker-compose up
echo "Telegram server stopped"