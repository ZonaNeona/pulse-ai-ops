#!/usr/bin/env bash
# Install a release built by `python tools/release.py` on the server (demo.shvarev-demo.ru).
#
#   scp pulse-release.tar.gz infra/deploy.sh root@server:/tmp/
#   ssh root@server 'bash /tmp/deploy.sh /tmp/pulse-release.tar.gz'
#
# Keeps what lives between releases: /etc/pulse/pulse.env (secrets), /opt/pulse/var (SQLite, LangGraph
# checkpoints) and the virtualenv. Code is owned by root and read-only for the service user.
set -euo pipefail

ARCHIVE=${1:-/tmp/pulse-release.tar.gz}
DEST=/opt/pulse
ENV_FILE=/etc/pulse/pulse.env
STAGE=$(mktemp -d)
trap 'rm -rf "$STAGE"' EXIT

echo "==> unpack"
tar -xzf "$ARCHIVE" -C "$STAGE"
mkdir -p "$DEST/apps/api" "$DEST/apps/web" "$DEST/var" /etc/pulse
[ -f "$ENV_FILE" ] || install -m 600 "$STAGE/.env.example" "$ENV_FILE"

echo "==> replace code (var/, .venv and secrets stay)"
rm -rf "$DEST/apps/api/pulse" "$DEST/hermes" "$DEST/infra"
# Hashed chunks of the previous releases stay a week: a tab opened before the release still loads its screens.
mkdir -p "$DEST/apps/web/dist/assets"
cp -a "$STAGE/apps/web/dist/assets/." "$DEST/apps/web/dist/assets/"
find "$DEST/apps/web/dist/assets" -type f -mtime +7 -delete
find "$STAGE/apps/web/dist" -maxdepth 1 -type f -exec cp -a {} "$DEST/apps/web/dist/" \;
cp -a "$STAGE/apps/api/pulse" "$DEST/apps/api/pulse"
cp -a "$STAGE/apps/api/pyproject.toml" "$DEST/apps/api/pyproject.toml"
cp -a "$STAGE/hermes" "$STAGE/infra" "$DEST/"
cp -a "$STAGE/.env.example" "$STAGE/README.md" "$STAGE/LICENSE" "$DEST/"

echo "==> permissions"
chown -R root:root "$DEST/apps" "$DEST/hermes" "$DEST/infra" "$DEST/.env.example" "$DEST/README.md" "$DEST/LICENSE"
find "$DEST/apps" "$DEST/hermes" "$DEST/infra" -type d -exec chmod 755 {} +
find "$DEST/apps" "$DEST/hermes" "$DEST/infra" -type f -not -path "*/.venv/*" -exec chmod 644 {} +
chmod 755 "$DEST"/infra/*.sh
chmod 644 "$DEST/.env.example" "$DEST/README.md" "$DEST/LICENSE"
chown -R www-data:www-data "$DEST/var"
chmod 600 "$ENV_FILE"

echo "==> python dependencies"
[ -d "$DEST/apps/api/.venv" ] || python3 -m venv "$DEST/apps/api/.venv"
"$DEST/apps/api/.venv/bin/pip" install -q -e "$DEST/apps/api"

echo "==> systemd and nginx"
install -m 644 "$DEST"/infra/systemd/pulse-*.service "$DEST"/infra/systemd/pulse-*.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable -q pulse-api.service pulse-reset.timer
install -m 644 "$DEST/infra/nginx/demo.shvarev-demo.ru.conf" /etc/nginx/sites-available/demo.shvarev-demo.ru
ln -sf /etc/nginx/sites-available/demo.shvarev-demo.ru /etc/nginx/sites-enabled/demo.shvarev-demo.ru
nginx -t -q && systemctl reload nginx

echo "==> restart and check"
systemctl restart pulse-api.service
systemctl restart pulse-reset.timer
# Hermes keeps its MCP server process alive between turns: restart it so it runs the new tool code.
if systemctl is-enabled -q pulse-hermes.service 2>/dev/null; then systemctl restart pulse-hermes.service; fi
for _ in $(seq 1 60); do
    curl -fsS http://127.0.0.1:8010/api/health >/dev/null 2>&1 && break
    sleep 2
done
curl -fsS http://127.0.0.1:8010/api/health || { journalctl -u pulse-api -n 40 --no-pager; exit 1; }
echo
curl -fsS -o /dev/null -w "overview %{http_code}\n" http://127.0.0.1:8010/api/overview
echo "deployed: $(python3 -c 'import json;print(json.load(open("/opt/pulse/apps/api/pulse/quality.json"))["commit"])')"
