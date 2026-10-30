FROM python:3.13-slim
WORKDIR /app
COPY sentinel /app/sentinel
RUN useradd --uid 10001 --create-home sentinel && mkdir -p /data && chown sentinel:sentinel /data
USER sentinel
ENV PYTHONUNBUFFERED=1
EXPOSE 8765
CMD ["python","-m","sentinel.api","--db","/data/sentinel.sqlite3","--host","0.0.0.0"]
