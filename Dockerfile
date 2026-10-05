# Start from an official image that already has Python installed
FROM python:3.12-slim

# All following commands run inside /app in the container
WORKDIR /app

# Install the project (engine and server) and its dependencies (fastapi, uvicorn)
COPY pyproject.toml ./
COPY src/ ./src/
RUN pip install --no-cache-dir .

# Document the port the server listens on
EXPOSE 8000

# Command that runs when the container starts
CMD ["uvicorn", "governancekit.server.main:app", "--host", "0.0.0.0", "--port", "8000"]
