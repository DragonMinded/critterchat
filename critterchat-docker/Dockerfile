FROM alpine

WORKDIR /app

COPY backend ./backend
COPY frontend ./frontend
COPY ./critterchat-docker/docker-entrypoint.sh ./backend/
RUN ls

# BACKEND
WORKDIR /app/backend
ENV PYTHONUNBUFFERED=1
RUN apk add --update --no-cache python3 py3-pip py3-mysqlclient ffmpeg
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt

# FRONTEND
WORKDIR /app/frontend
RUN apk add --update --no-cache nodejs npm
RUN npm install
RUN npm run build

# RUN
WORKDIR /app/backend
CMD ["sh", "./docker-entrypoint.sh"]
