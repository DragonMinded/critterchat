FROM python:3.14-alpine
WORKDIR /usr/src/app
RUN apk add --no-cache pkgconf mariadb-connector-c-dev build-base 
RUN mkdir ./backend
WORKDIR /usr/src/app/backend
COPY /backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

WORKDIR /usr/src/app
COPY /backend ./backend
COPY /frontend ./frontend
WORKDIR /usr/src/app/backend
CMD [ "python", "-m", "critterchat", "--debug"]
