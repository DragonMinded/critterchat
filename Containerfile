FROM node:25-alpine
WORKDIR /src
COPY /frontend ./frontend
WORKDIR /src/frontend
RUN mkdir -p /src/backend/critterchat/http/static
RUN npm ci && npm run build


FROM python:3.14-alpine
WORKDIR /usr/src/app
RUN apk add --no-cache pkgconf mariadb-connector-c-dev build-base 
RUN mkdir ./backend
WORKDIR /usr/src/app/backend
COPY /backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

WORKDIR /usr/src/app
COPY /backend ./backend
COPY --from=0 /src/backend/critterchat/http/static ./backend/critterchat/http/static
WORKDIR /usr/src/app/backend

# TODO build the frontend, maybe in a separate container with a node environment

CMD [ "python", "-m", "critterchat", "-c", "/usr/src/app/backend/config.yaml", "--debug"]
