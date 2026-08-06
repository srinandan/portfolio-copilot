# Build stage
FROM node:22-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

# Final stage
FROM nginx:alpine-slim

# Template is evaluated by nginx entrypoint envsubst at container startup using injected environment variables (PROJECT_NUMBER, REGION)
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=builder /app/dist /usr/share/nginx/html

ENV NGINX_ENVSUBST_OUTPUT_DIR=/etc/nginx/conf.d

EXPOSE 8080
CMD ["nginx", "-g", "daemon off;"]
