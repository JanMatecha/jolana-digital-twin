#!/bin/sh
set -e

APP_DIR="/volume1/docker/jolana-digital-twin"
APP_URL="http://192.168.1.14:8501"
CONTAINER_NAME="jolana-digital-twin"

sudo -v

cd "$APP_DIR"

git pull

sudo docker-compose down
sudo docker-compose up -d --build
sudo docker ps

sudo docker exec -it "$CONTAINER_NAME" omc --version
sudo docker exec -it "$CONTAINER_NAME" omc --eval='loadModel(Modelica); getErrorString();'

printf '\nApplication URL: %s\n' "$APP_URL"
