# Use official Python image
FROM python:3.10

# Set the working directory
WORKDIR /app

# Copy everything to the container
COPY . .

# Install dependencies
RUN pip install --no-cache-dir --upgrade pip \
    && pip install -r requirements.txt

# Expose FastAPI port
EXPOSE 8000

# Run FastAPI app
CMD ["python3", "main.py"]
