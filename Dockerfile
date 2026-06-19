FROM python:3.11-slim

# PyMuPDF needs libmupdf; also need gcc for some Presidio native deps
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download spaCy model at build time so runtime has zero download delay.
# en_core_web_lg gives the best NER for names/locations (GDPR-critical accuracy).
# Switch to en_core_web_md for a faster/smaller build at some accuracy cost.
RUN python -m spacy download en_core_web_lg
RUN python -m spacy download nb_core_news_lg

COPY . .
RUN pip install --no-cache-dir --no-deps .

RUN mkdir -p /app/safe-output/logs

ENTRYPOINT ["safe"]
