FROM python:3.11-slim

WORKDIR /app

ENV PIP_NO_CACHE_DIR=1

COPY requirements.runtime.txt .
RUN pip install -r requirements.runtime.txt

COPY . .
