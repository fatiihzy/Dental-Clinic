# Gunakan image Python
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Copy semua file ke image
COPY . .

# Install dependency
RUN pip install --no-cache-dir --upgrade pip setuptools wheel
RUN pip install rasa==3.5.10

# Jalankan Rasa server
CMD ["rasa", "run", "--enable-api", "--cors", "*", "--debug"]
