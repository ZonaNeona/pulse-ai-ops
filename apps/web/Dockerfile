# Build stage
FROM node:22-alpine AS builder

WORKDIR /app
COPY apps/web/package*.json ./
RUN npm ci

COPY apps/web ./
RUN npm run build

# Production stage
FROM nginx:alpine

COPY --from=builder /app/dist /usr/share/nginx/html

RUN cat <<'EOF' > /etc/nginx/conf.d/default.conf
server {
    listen 80;
    server_name localhost;

    location /api/ {
        proxy_pass http://api:8010;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location / {
        root /usr/share/nginx/html;
        try_files $uri $uri/ /index.html;
    }
}
EOF

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
