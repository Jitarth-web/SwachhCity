FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for AI/ML
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libgthread-2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create models directory
RUN mkdir -p /app/models

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 8001

# Run the application
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8001", "--reload"]
