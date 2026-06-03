FROM python:3.14-slim

# Install system dependencies
# We need curl for Node.js, plus basic build tools
RUN apt-get update && apt-get install -y \
    curl \
    gnupg \
    build-essential \
    libpq-dev \
    libcairo2 \
    libcairo2-dev \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    shared-mime-info \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js (required for Playwright MCP / npx)
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get update \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install Playwright dependencies and browsers
# This ensures that when the Agent runs `npx @playwright/mcp`, the system dependencies are present.
RUN npx -y playwright install --with-deps chrome

# Install uv (Python package manager)
RUN curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin sh

# Set working directory
WORKDIR /app

# Copy dependency files first to leverage Docker cache
COPY pyproject.toml uv.lock ./

# Install dependencies using uv
# We create a virtual environment inside /app/.venv
RUN uv sync --frozen

# Copy the rest of the application
COPY . .

# Ensure generated directories exist (they will be mounted, but good to have)
RUN mkdir -p generated_pdfs generated_excels

# Environment variables
# The PATH ensures we use the uv virtual environment
ENV PATH="/app/.venv/bin:$PATH"
# Prevent python from buffering stdout (better logging)
ENV PYTHONUNBUFFERED=1

# Command to run the application
CMD ["python", "main.py"]
