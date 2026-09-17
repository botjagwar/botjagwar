#!/bin/bash
set -Eeuo pipefail

src_dir=$(cd "$(dirname "$0")" && pwd)
install_dir=${ATLAS_INSTALL_DIR:-/opt/botjagwar-front}
config_dir=${ATLAS_CONFIG_DIR:-/etc/botjagwar/nginx}
state_dir=${ATLAS_STATE_DIR:-/var/lib/botjagwar/atlas}
legacy_install_dir=${ATLAS_LEGACY_INSTALL_DIR:-/opt/botjagwar-front}
certificate_dir=${ATLAS_CERTIFICATE_DIR:-/opt/botjagwar-certs}
current_user=$(whoami)
current_group=$(id -gn)
botjagwar_config=${BOTJAGWAR_CONFIG:-/etc/botjagwar/config.ini}

if ! command -v openssl >/dev/null 2>&1; then
    sudo apt-get update
    sudo apt-get install -y openssl
fi

node_major=0
if command -v node >/dev/null 2>&1; then
    node_major=$(node -p "process.versions.node.split('.')[0]")
fi

if ! command -v npm >/dev/null 2>&1 || (( node_major < 22 )); then
    echo "Installing Node.js 22 and npm"
    sudo apt-get update
    sudo apt-get install -y ca-certificates curl gnupg
    sudo install -d -m 0755 /etc/apt/keyrings
    curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key \
        | sudo gpg --dearmor --yes -o /etc/apt/keyrings/nodesource.gpg
    printf '%s\n' "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_22.x nodistro main" \
        | sudo tee /etc/apt/sources.list.d/nodesource.list >/dev/null
    sudo apt-get update
    sudo apt-get install -y nodejs
fi

if ! command -v node >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1; then
    echo "Node.js installation failed."
    exit 1
fi

node_major=$(node -p "process.versions.node.split('.')[0]")
if (( node_major < 22 )); then
    echo "Node.js 22 or later is required. Found $(node --version)."
    exit 1
fi

cd "$src_dir"
npm ci
npm run build

sudo mkdir -p "$install_dir/config/nginx" "$install_dir/logs"
sudo mkdir -p "$config_dir" "$state_dir/logs" /etc/botjagwar
if [[ ! -e /etc/botjagwar/supervisor-rpc-location.conf ]]; then
    legacy_rpc_location="$install_dir/config/nginx/supervisor-rpc-location.conf"
    if [[ -s $legacy_rpc_location ]]; then
        sudo install -o root -g root -m 0644 "$legacy_rpc_location" /etc/botjagwar/supervisor-rpc-location.conf
    else
        sudo install -o root -g root -m 0644 /dev/null /etc/botjagwar/supervisor-rpc-location.conf
    fi
fi
render_runtime_config() {
    local destination=$1
    local fallback=$2
    BOTJAGWAR_CONFIG="$botjagwar_config" \
        FALLBACK_CONFIG="$fallback" \
        python3 - "$destination" <<'PY'
import json
import os
import re
import sys
from pathlib import Path

destination = Path(sys.argv[1])
fallback_path = Path(os.environ["FALLBACK_CONFIG"])
try:
    with fallback_path.open(encoding="utf-8") as fallback_file:
        config = json.load(fallback_file)
except (FileNotFoundError, json.JSONDecodeError):
    config = {}

config.setdefault("databaseAddress", "")
config.setdefault("postgrestAddresses", ["/api/database"])
config.setdefault("dictionaryServiceAddresses", ["/api/dictionary"])
config.setdefault("entryTranslatorAddresses", ["/api/translator"])

try:
    content = Path(os.environ["BOTJAGWAR_CONFIG"]).read_text(encoding="utf-8")
except OSError:
    content = ""
match = re.search(r"(?m)^\s*postgrest_backend_address\s*=\s*([^\s#;]+)", content)
if match:
    backend = match.group(1).rstrip("/")
    config["databaseAddress"] = f"{backend}/botjagwar"

destination.parent.mkdir(parents=True, exist_ok=True)
destination.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
PY
}

sudo cp -R "$src_dir/dist/." "$install_dir/"
if [[ ! -f /etc/botjagwar/atlas-config.json ]]; then
    runtime_config_source="$install_dir/config.json"
    if [[ -f $legacy_install_dir/config.json ]]; then
        runtime_config_source="$legacy_install_dir/config.json"
    fi
    if [[ -f $runtime_config_source ]]; then
        runtime_config_temp=$(mktemp)
        render_runtime_config "$runtime_config_temp" "$runtime_config_source"
        sudo install -o "$current_user" -g "$current_group" -m 0640 \
            "$runtime_config_temp" /etc/botjagwar/atlas-config.json
        rm -f "$runtime_config_temp"
    fi
fi
sudo rm -f "$install_dir/config.json"
sudo ln -s /etc/botjagwar/atlas-config.json "$install_dir/config.json"
sudo rm -rf "$install_dir/logs"
sudo ln -s "$state_dir/logs" "$install_dir/logs"
sudo cp "$src_dir/config/nginx/nginx.conf" "$install_dir/config/nginx/nginx.conf"
for upstream_file in postgrest-upstreams.conf dictionary-service-upstreams.conf entry-translator-upstreams.conf supervisor-control-upstreams.conf; do
    if [[ ! -f "$config_dir/$upstream_file" ]]; then
        if [[ -f $legacy_install_dir/config/nginx/$upstream_file ]]; then
            sudo cp "$legacy_install_dir/config/nginx/$upstream_file" "$config_dir/$upstream_file"
        else
            sudo cp "$src_dir/config/nginx/$upstream_file" "$config_dir/$upstream_file"
        fi
    fi
done
if [[ ! -f "$config_dir/atlas.htpasswd" ]]; then
    if [[ -f $legacy_install_dir/config/nginx/atlas.htpasswd ]]; then
        sudo cp "$legacy_install_dir/config/nginx/atlas.htpasswd" "$config_dir/atlas.htpasswd"
        sudo chmod 0600 "$config_dir/atlas.htpasswd"
    else
        initial_username=${ATLAS_USERNAME:-atlas}
        if [[ ! $initial_username =~ ^[A-Za-z0-9_.-]+$ ]]; then
            echo "ATLAS_USERNAME may contain only letters, numbers, dots, underscores, and hyphens."
            exit 1
        fi
        initial_password=${ATLAS_PASSWORD:-$(openssl rand -base64 24 | tr -d '\n')}
        password_hash=$(openssl passwd -6 -stdin <<< "$initial_password")
        printf '%s:%s\n' "$initial_username" "$password_hash" | sudo tee "$config_dir/atlas.htpasswd" >/dev/null
        sudo chmod 0600 "$config_dir/atlas.htpasswd"
        credentials_created=1
    fi
fi
sudo cp "$src_dir/configure-atlas.sh" "$install_dir/configure-atlas.sh"
sudo cp "$src_dir/setup-tls.sh" "$install_dir/setup-tls.sh"
sudo chmod 0755 "$install_dir/configure-atlas.sh"
sudo chmod 0755 "$install_dir/setup-tls.sh"
if [[ ${ATLAS_STAGE_ONLY:-0} == 1 ]]; then
    echo "Atlas release staged; TLS setup is deferred until activation."
elif [[ -d $certificate_dir && -r $certificate_dir/fullchain.pem && -r $certificate_dir/privkey.pem ]]; then
    echo "Reusing the existing Atlas certificate in $certificate_dir; skipping certificate generation."
else
    ATLAS_INSTALL_DIR="$install_dir" ATLAS_CERTIFICATE_DIR="$certificate_dir" bash "$src_dir/setup-tls.sh"
fi
sudo chown -R "$current_user":"$current_group" "$install_dir" "$state_dir"
sudo chown -R "$current_user":"$current_group" "$config_dir"
if [[ ${ATLAS_STAGE_ONLY:-0} != 1 ]]; then
    /usr/sbin/nginx -t -p "$install_dir/" -c "$install_dir/config/nginx/nginx.conf"
fi

echo "Frontend installed in $install_dir"
if [[ ${credentials_created:-0} == 1 ]]; then
    echo "Atlas username: $initial_username"
    echo "Atlas password: $initial_password"
    echo "Store this password securely; it will not be shown again."
fi
