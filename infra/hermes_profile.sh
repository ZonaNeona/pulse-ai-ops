#!/usr/bin/env bash
# Install / refresh the Hermes Agent profile «pulse»: API server on 127.0.0.1:8663, the stand's tools over
# MCP (infra/mcp.sh → pulse.agents.mcp_server), persona and skills from hermes/. Idempotent.
# Touches only: the profile dir, /etc/pulse/pulse.env (HERMES_* lines), pulse-hermes.service, ACL on /opt/pulse/var.
set -euo pipefail

H=/home/hermes/.hermes
P=$H/profiles/pulse
HB=/home/hermes/.local/bin/hermes
ENV_FILE=/etc/pulse/pulse.env
PORT=8663
MODEL=${PULSE_HERMES_MODEL:-deepseek/deepseek-chat}

KEY_LLM=$(grep -E '^LLM_API_KEY=' "$ENV_FILE" | cut -d= -f2-)
BASE=$(grep -E '^LLM_BASE_URL=' "$ENV_FILE" | cut -d= -f2-)
[ -n "$KEY_LLM" ] || { echo "LLM_API_KEY missing in $ENV_FILE"; exit 1; }
BASE=${BASE:-https://openrouter.ai/api/v1}

# The MCP server runs as user hermes: it reads the code and writes drafts into the stand's SQLite.
setfacl -R -m u:hermes:rwX /opt/pulse/var
setfacl -R -d -m u:hermes:rwX,u:www-data:rwX /opt/pulse/var

[ -d "$P" ] || sudo -u hermes -H HERMES_HOME=$H $HB profile create pulse --no-alias --no-skills >/dev/null
CV=$(grep -E '^_config_version:' "$P/config.yaml" 2>/dev/null | awk '{print $2}' || true)
cat > "$P/config.yaml" <<EOF
model:
  default: $MODEL
  provider: openrouter
  base_url: $BASE
agent:
  reasoning_effort: "none"
  api_max_retries: 1
  auto_recovery_cycles: 1
providers:
  openrouter:
    request_timeout_seconds: 60
tools:
  tool_search:
    enabled: "off"
gateway:
  standalone: true
platform_toolsets:
  cli: [skills]
  api_server: [skills]
mcp_servers:
  pulse:
    command: /opt/pulse/infra/mcp.sh
    timeout: 60
_config_version: ${CV:-49}
EOF

API_KEY=$(grep -E '^API_SERVER_KEY=' "$P/.env" 2>/dev/null | cut -d= -f2- || true)
[ -n "$API_KEY" ] || API_KEY=$(openssl rand -hex 24)
printf 'OPENROUTER_API_KEY=%s\nOPENROUTER_BASE_URL=%s\nAPI_SERVER_ENABLED=true\nAPI_SERVER_HOST=127.0.0.1\nAPI_SERVER_PORT=%s\nAPI_SERVER_KEY=%s\n' \
  "$KEY_LLM" "$BASE" "$PORT" "$API_KEY" > "$P/.env"

cp /opt/pulse/hermes/SOUL.md "$P/SOUL.md"
mkdir -p "$P/skills"
rm -rf "$P"/skills/pulse-*
cp -r /opt/pulse/hermes/skills/pulse-* "$P/skills/"
chown -R hermes:hermes "$P"
chmod 600 "$P/config.yaml" "$P/.env"

sed -i '/^HERMES_API_URL=/d;/^HERMES_API_KEY=/d' "$ENV_FILE"
printf 'HERMES_API_URL=http://127.0.0.1:%s\nHERMES_API_KEY=%s\n' "$PORT" "$API_KEY" >> "$ENV_FILE"
chmod 600 "$ENV_FILE"

install -m 644 /opt/pulse/infra/systemd/pulse-hermes.service /etc/systemd/system/pulse-hermes.service
systemctl daemon-reload
systemctl enable -q pulse-hermes.service
systemctl restart pulse-hermes.service
for _ in $(seq 1 60); do
  curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT/health" 2>/dev/null | grep -q 200 && break
  sleep 1
done
echo "hermes api: $(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT/health") model=$MODEL"
systemctl restart pulse-api.service
