#!/usr/bin/env bash
# Deploy / update Pulse AI Ops on 159.194.250.138 (demo.shvarev-demo.ru)
set -euo pipefail

DEST="/opt/pulse"
ENV_FILE="/etc/pulse/pulse.env"

echo "==> [1/6] Ensuring base directories and permissions"
mkdir -p "$DEST" "/etc/pulse" "$DEST/var"
chown -R www-data:www-data "$DEST/var"

if [ ! -f "$ENV_FILE" ]; then
    echo "Creating initial $ENV_FILE from .env.example"
    cp "$DEST/.env.example" "$ENV_FILE"
    chmod 600 "$ENV_FILE"
fi

echo "==> [2/6] Setting up Python 3.12 virtualenv"
if [ ! -d "$DEST/apps/api/.venv" ]; then
    python3 -m venv "$DEST/apps/api/.venv"
fi
"$DEST/apps/api/.venv/bin/pip" install --upgrade pip
"$DEST/apps/api/.venv/bin/pip" install -e "$DEST/apps/api"

echo "==> [3/6] Installing systemd units"
cp "$DEST/infra/systemd/pulse-api.service" /etc/systemd/system/pulse-api.service
cp "$DEST/infra/systemd/pulse-reset.service" /etc/systemd/system/pulse-reset.service
cp "$DEST/infra/systemd/pulse-reset.timer" /etc/systemd/system/pulse-reset.timer
systemctl daemon-reload
systemctl enable pulse-api.service
systemctl enable pulse-reset.timer

echo "==> [4/6] Configuring Nginx and SSL"
cp "$DEST/infra/nginx/demo.shvarev-demo.ru.conf" /etc/nginx/sites-available/demo.shvarev-demo.ru
ln -sf /etc/nginx/sites-available/demo.shvarev-demo.ru /etc/nginx/sites-enabled/demo.shvarev-demo.ru

# If certificate does not exist yet, issue it via certbot
if [ ! -d "/etc/letsencrypt/live/demo.shvarev-demo.ru" ]; then
    echo "Issuing Let's Encrypt certificate for demo.shvarev-demo.ru..."
    # Temporarily allow http-only challenge verification
    nginx -t && systemctl reload nginx
    certbot certonly --nginx -d demo.shvarev-demo.ru --non-interactive --agree-tos --register-unsafely-without-email
fi

nginx -t
systemctl reload nginx

echo "==> [5/6] Restarting Pulse API"
systemctl restart pulse-api.service
systemctl restart pulse-reset.timer

echo "==> [6/6] Verifying health check"
sleep 2
curl -fsS http://127.0.0.1:8010/api/health || {
    echo "Health check failed! Journal logs:"
    journalctl -u pulse-api -n 25 --no-pager
    exit 1
}

echo "Pulse AI Ops successfully deployed and running at https://demo.shvarev-demo.ru"
