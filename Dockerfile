FROM dailyco/pipecat-base:latest

COPY pyproject.toml .
RUN uv sync

COPY ./bot.py bot.py
