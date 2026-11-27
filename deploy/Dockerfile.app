# GridPulse app image: Streamlit dashboard and the one-shot database init (gridpulse-init).
FROM python:3.12.8-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /opt/gridpulse
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install -e ".[app]"
COPY app ./app
COPY config ./config
COPY db ./db
RUN useradd --uid 10001 --create-home gridpulse && chown -R gridpulse /opt/gridpulse
USER gridpulse
EXPOSE 8501
CMD ["streamlit", "run", "app/app.py", "--server.port=8501", "--server.address=0.0.0.0", \
     "--server.headless=true", "--browser.gatherUsageStats=false"]
