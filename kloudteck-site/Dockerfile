FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
# Postgres এর জন্য লাইব্রেরি ইনস্টল
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install gunicorn psycopg2-binary

COPY . .

# পোর্ট 9০০০ এক্সপোজ করা
EXPOSE 9000

# অ্যাপ রান করা
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:9000", "app:app"]