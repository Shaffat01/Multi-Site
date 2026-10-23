# veranda-django/Dockerfile
FROM python:3.10-slim 

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /app

# Install dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . /app/

# Collect static files
RUN python manage.py collectstatic --noinput

EXPOSE 9000

# Gunicorn 
CMD ["gunicorn", "--bind", "0.0.0.0:9000", "veranda_project.wsgi:application"]
