# Stage 1: Build the Vue SPA frontend
FROM node:20-alpine AS ui-builder
WORKDIR /app
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Build the Go backend server
FROM golang:1.26.6 AS go-builder
WORKDIR /app

COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -o /app/server-bin ./frontend/server

# Stage 3: Minimal static runtime container
FROM gcr.io/distroless/static:nonroot
WORKDIR /app

COPY --from=go-builder /app/server-bin /app/server
COPY --from=ui-builder /app/dist /app/dist

ENV STATIC_DIR=/app/dist
USER nonroot:nonroot
EXPOSE 8080

ENTRYPOINT ["/app/server"]
