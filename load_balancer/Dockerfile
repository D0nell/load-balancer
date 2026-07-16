FROM python:3.10-slim

RUN apt-get update && apt-get install -y \
    curl \
    sudo \
    && curl -fsSL https://get.docker.com -o get-docker.sh \
    && sh get-docker.sh \
    && rm -rf /var/lib/apt/lists/*

RUN echo "root ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt


COPY consistent_hash.py .
COPY load_balancer.py .

EXPOSE 5000

CMD ["python", "load_balancer.py"]