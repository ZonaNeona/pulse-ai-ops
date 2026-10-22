#!/bin/bash
# Install / refresh the Hermes profile «pulse» (API server + FastMCP tools)
# Runs as systemd service pulse-hermes on 127.0.0.1:8663
set -euo pipefail

H=/home/hermes/.hermes
P=$H/profiles/pulse
HB=/home/hermes/.local/bin/hermes
PORT=8663
MODEL=${PULSE_HERMES_MODEL:-deepseek/deepseek-chat}

if [ ! -d "/home/hermes" ]; then
    echo "Hermes user directory not found, skipping Hermes profile creation"
    exit 0
fi

OPENROUTER_API_KEY=$(grep -E '^LLM_API_KEY=' /etc/pulse/pulse.env | cut -d= -f2- || true)
OPENROUTER_BASE_URL=$(grep -E '^LLM_BASE_URL=' /etc/pulse/pulse.env | cut -d= -f2- || echo "https://openrouter.ai/api/v1")

if [ ! -d "$P" ]; then
    sudo -u hermes -H HERMES_HOME=$H $HB profile create pulse --no-alias --no-skills >/dev/null || true
fi

mkdir -p "$P"

cat > "$P/config.yaml" <<EOF
model:
  default: $MODEL
  provider: openrouter
  base_url: $OPENROUTER_BASE_URL
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
EOF

KEY=$(grep -E '^API_SERVER_KEY=' "$P/.env" 2>/dev/null | cut -d= -f2- || true)
[ -n "$KEY" ] || KEY=$(openssl rand -hex 24)

printf 'OPENROUTER_API_KEY=%s\nOPENROUTER_BASE_URL=%s\nAPI_SERVER_ENABLED=true\nAPI_SERVER_HOST=127.0.0.1\nAPI_SERVER_PORT=%s\nAPI_SERVER_KEY=%s\n' \
  "$OPENROUTER_API_KEY" "$OPENROUTER_BASE_URL" "$PORT" "$KEY" > "$P/.env"

if [ -f /opt/pulse/hermes/SOUL.md ]; then
    cp /opt/pulse/hermes/SOUL.md "$P/SOUL.md"
fi

mkdir -p "$P/skills"
if [ -d /opt/pulse/hermes/skills ]; then
    cp -r /opt/pulse/hermes/skills/* "$P/skills/" || true
fi

chown -R hermes:hermes "$P" || true
chmod 600 "$P/config.yaml" "$P/.env" || true

# Update /etc/pulse/pulse.env with the connection settings
sed -i '/^HERMES_API_URL=/d' /etc/pulse/pulse.env
sed -i '/^HERMES_API_KEY=/d' /etc/pulse/pulse.env
echo "HERMES_API_URL=http://127.0.0.1:$PORT" >> /etc/pulse/pulse.env
echo "HERMES_API_KEY=$KEY" >> /etc/pulse/pulse.env

echo "Hermes profile 'pulse' configured on port $PORT"
