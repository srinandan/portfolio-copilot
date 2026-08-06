# Stage 1: build the Vue SPA
FROM node:22-alpine AS ui-builder

WORKDIR /ui

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# Stage 2: build the Go server (static-file host + authed proxy to gateway)
FROM golang:1.25 AS go-builder

WORKDIR /app

COPY go.mod go.sum ./
RUN go mod download

COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -o /app/frontend-bin ./frontend/server

# Stage 3: distroless runtime
FROM gcr.io/distroless/static:nonroot

WORKDIR /

COPY --from=go-builder /app/frontend-bin /frontend
COPY --from=ui-builder /ui/dist /dist

ENV STATIC_DIR=/dist

USER nonroot:nonroot

EXPOSE 8080

ENTRYPOINT ["/frontend"]
