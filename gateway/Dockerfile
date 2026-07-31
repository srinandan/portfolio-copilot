# Build stage
FROM golang:1.25 AS builder

WORKDIR /app

# Copy the go mod files from the root
COPY go.mod go.sum ./

# Download dependencies
RUN go mod download

# Copy the entire project
COPY . .

# Build the gateway
RUN CGO_ENABLED=0 GOOS=linux go build -o /app/gateway-bin ./gateway/main.go

# Final stage
FROM gcr.io/distroless/static:nonroot

WORKDIR /

# Copy binary from builder
COPY --from=builder /app/gateway-bin /gateway

# Use nonroot user
USER nonroot:nonroot

EXPOSE 8080

ENTRYPOINT ["/gateway"]
