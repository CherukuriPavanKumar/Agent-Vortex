FROM golang:1.25

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libc6-dev \
    git \
    curl


# Copy source code
COPY . .

# Download dependencies
RUN go mod download

# Build the application
ENV CGO_ENABLED=1

RUN mkdir -p bin && \
    go build -o ./bin/whatsapp-mcp ./cmd/whatsapp-mcp

# Command to run the executable
CMD ["./bin/whatsapp-mcp", "serve"]
