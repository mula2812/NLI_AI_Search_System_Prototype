FROM python:3.11-slim-bookworm

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get upgrade -y && apt-get install -y \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

# Copy application files
COPY mcp_tool.py .
COPY ui.py .
COPY openapi_schema.json .

# Install Python dependencies
RUN pip install --no-cache-dir \
    fastapi \
    uvicorn \
    httpx \
    streamlit \
    google-generativeai

# Expose ports for FastAPI (8000) and Streamlit (8501)
EXPOSE 8000 8501

COPY start.sh .
RUN chmod +x start.sh
RUN sed -i 's/\r$//' start.sh

CMD ["./start.sh"]
