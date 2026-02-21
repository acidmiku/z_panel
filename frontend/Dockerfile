# Stage 1: Build
FROM node:20-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .
RUN npm run build

# Stage 2: Serve
FROM nginx:1.27-alpine

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Run as non-root
RUN chown -R nginx:nginx /usr/share/nginx/html /var/cache/nginx /var/log/nginx && \
    touch /var/run/nginx.pid && chown nginx:nginx /var/run/nginx.pid

USER nginx

EXPOSE 8080
