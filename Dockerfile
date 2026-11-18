FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends poppler-utils tesseract-ocr tesseract-ocr-por && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY static ./static
COPY examples ./examples
COPY gunicorn.conf.py config.json ./
RUN useradd --create-home clareza
USER clareza
CMD ["gunicorn", "--config", "gunicorn.conf.py", "app.wsgi:application"]
