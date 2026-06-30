FROM python:3.10-slim

WORKDIR /app

RUN pip install --no-cache-dir flask

COPY server.py app.py

ENV SERVER_ID=unknown

EXPOSE 5000

CMD ["python", "app.py"]