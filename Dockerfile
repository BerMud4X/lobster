FROM python:3.12

# Set working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Default command — run the ETL pipeline
CMD ["python", "backend/src/main.py"]
