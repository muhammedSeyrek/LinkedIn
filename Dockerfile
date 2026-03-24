# ── Build stage ──────────────────────────────────────────────────────────────
FROM golang:1.21-bookworm AS builder
WORKDIR /build
COPY go.mod ./
COPY *.go ./
RUN go mod tidy && CGO_ENABLED=0 GOOS=linux go build -o linkedin-scraper .

# ── Runtime stage ─────────────────────────────────────────────────────────────
FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y \
    chromium \
    ca-certificates \
    fonts-liberation \
    --no-install-recommends \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=builder /build/linkedin-scraper .
COPY templates ./templates
COPY static    ./static
RUN mkdir -p logs static/results temp

ENV CHROME_BIN=/usr/bin/chromium
ENV GIN_MODE=release
EXPOSE 5000
CMD ["./linkedin-scraper"]
