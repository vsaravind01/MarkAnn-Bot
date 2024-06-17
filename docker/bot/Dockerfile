FROM python:3.12-alpine

WORKDIR /app

RUN apk add g++

COPY requirements.txt /app/requirements.txt

RUN pip install -r /app/requirements.txt

COPY bot /app/bot
COPY channels /app/channels
COPY common_managers /app/common_managers
COPY database /app/database

CMD ["python", "-m", "bot.app"]
