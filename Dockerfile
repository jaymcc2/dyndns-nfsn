FROM python:3.13-slim

WORKDIR /app

RUN mkdir -p /config /logs

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY wsgi.py .
COPY dyndns_nfsn.py .
COPY dyndns_nfsn/ ./dyndns_nfsn/
COPY start.sh .

# Runs as an unprivileged user; TrueNAS can still override via container config.
RUN useradd --create-home --shell /usr/sbin/nologin appuser && \
    chown -R appuser:appuser /config /logs /app/start.sh
USER appuser

EXPOSE 80

# Fails if the main loop hasn't written a heartbeat within 3 check intervals (stalled/crashed).
HEALTHCHECK --interval=60s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import os,sys,time; p='/tmp/healthy'; sys.exit(0 if os.path.exists(p) and time.time() - os.path.getmtime(p) < int(os.getenv('CHECK_INTERVAL','300')) * 3 else 1)"

CMD ["./start.sh"]
