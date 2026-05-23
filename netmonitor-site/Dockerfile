FROM python:3.11-slim

WORKDIR /app

# System dependencies
# - iputils-ping: fallback ping er jonno
# - libcap2-bin: setcap er jonno (raw socket permission)
# - gcc, libpq-dev: psycopg2 build
RUN apt-get update && apt-get install -y --no-install-recommends \
    iputils-ping \
    libcap2-bin \
    gcc \
    g++ \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Python binary ke raw socket use korar permission diye dei
# Eta icmplib privileged mode e kaj korar jonno proyojon
RUN setcap cap_net_raw+ep /usr/local/bin/python3.11

# Application code copy
COPY . .

# Required folders
RUN mkdir -p uploads && chmod 755 uploads

# Port expose
EXPOSE 3000

# Gunicorn - SINGLE WORKER (APScheduler er jonno MUST!)
CMD ["gunicorn", \
     "--bind", "0.0.0.0:3000", \
     "--workers", "1", \
     "--threads", "8", \
     "--timeout", "120", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "app:app"]