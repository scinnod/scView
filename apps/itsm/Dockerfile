FROM python:3.11-slim

# Install system dependencies in a single layer to reduce image size
# - texlive packages for LaTeX document generation (PDF exports)
# - build-essential and libpq-dev for PostgreSQL driver compilation
# - xmlsec1 for XML security operations
# - netcat-openbsd for database health checks in entrypoint
RUN apt-get update && apt-get install -y --no-install-recommends \
    texlive-base \
    texlive-plain-generic \
    texlive-latex-extra \
    texlive-fonts-recommended \
    texlive-fonts-extra \
    texlive-lang-english \
    texlive-lang-german \
    latexmk \
    build-essential \
    libpq-dev \
    python3-dev \
    libsasl2-dev \
    libssl-dev \
    xmlsec1 \
    gettext \
    netcat-openbsd \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Create directory for static files (outside /app to avoid clutter)
RUN mkdir -p /var/www/staticfiles

# Copy and install Python dependencies first (better layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy entrypoint script
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

# Copy application code into the image
COPY . .

ENTRYPOINT ["./entrypoint.sh"]
