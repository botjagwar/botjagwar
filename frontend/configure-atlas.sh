#!/bin/bash
set -euo pipefail

install_dir=${ATLAS_INSTALL_DIR:-/opt/botjagwar/current/frontend}
botjagwar_config=${BOTJAGWAR_CONFIG:-/etc/botjagwar/config.ini}
postgrest_config_dir=${POSTGREST_CONFIG_DIR:-/etc/botjagwar/pgrest}
nginx_dir=${ATLAS_NGINX_CONFIG_DIR:-/etc/botjagwar/nginx}
nginx_config="$install_dir/config/nginx/nginx.conf"
runtime_config=${ATLAS_RUNTIME_CONFIG:-/etc/botjagwar/atlas-config.json}

database_uri=""
postgrest_addresses=""
dictionary_addresses=""
translator_addresses=""
atlas_username=""
atlas_password=""
password_stdin=0
database_uri_stdin=0
interactive=0

usage() {
    printf '%s\n' \
        "Usage: configure-atlas.sh [options]" \
        "" \
        "Options:" \
        "  --database-uri URI          SQLAlchemy database URI used by Botjagwar" \
        "  --database-uri-stdin        Read the SQLAlchemy database URI from standard input" \
        "  --postgrest ADDRESSES       Comma-separated PostgREST URLs or host:port values" \
        "  --dictionary-service ADDRESSES" \
        "                              Comma-separated dictionary_service addresses" \
        "  --entry-translator ADDRESSES" \
        "                              Comma-separated entry_translator addresses" \
        "  --username USERNAME         HTTP Basic Authentication username" \
        "  --password-stdin            Read the HTTP password from standard input" \
        "  --interactive               Prompt for every setting" \
        "  --help                      Show this help"
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --database-uri)
            database_uri=${2:?Missing value for --database-uri}
            shift 2
            ;;
        --database-uri-stdin)
            database_uri_stdin=1
            shift
            ;;
        --postgrest)
            postgrest_addresses=${2:?Missing value for --postgrest}
            shift 2
            ;;
        --dictionary-service)
            dictionary_addresses=${2:?Missing value for --dictionary-service}
            shift 2
            ;;
        --entry-translator)
            translator_addresses=${2:?Missing value for --entry-translator}
            shift 2
            ;;
        --username)
            atlas_username=${2:?Missing value for --username}
            shift 2
            ;;
        --password-stdin)
            password_stdin=1
            shift
            ;;
        --interactive)
            interactive=1
            shift
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

if [[ $database_uri_stdin == 1 && $password_stdin == 1 ]]; then
    echo "Database URI and HTTP password cannot both be read from standard input." >&2
    exit 2
fi

if [[ $interactive == 1 ]]; then
    read -r -p "Database URI (leave empty to keep current): " database_uri
    read -r -p "PostgREST addresses, comma-separated (leave empty to keep current): " postgrest_addresses
    read -r -p "Dictionary service addresses, comma-separated (leave empty to keep current): " dictionary_addresses
    read -r -p "Entry translator addresses, comma-separated (leave empty to keep current): " translator_addresses
    read -r -p "Atlas username (leave empty to keep current): " atlas_username
    read -r -s -p "Atlas password (leave empty to keep current): " atlas_password
    printf '\n'
elif [[ $database_uri_stdin == 1 ]]; then
    IFS= read -r database_uri
elif [[ $password_stdin == 1 ]]; then
    IFS= read -r atlas_password
fi

if [[ $password_stdin == 1 && -z $atlas_password ]]; then
    echo "The password read from standard input cannot be empty." >&2
    exit 2
fi

if [[ $database_uri_stdin == 1 && -z $database_uri ]]; then
    echo "The database URI read from standard input cannot be empty." >&2
    exit 2
fi

if [[ -n $atlas_username && ! $atlas_username =~ ^[A-Za-z0-9_.-]+$ ]]; then
    echo "Username may contain only letters, numbers, dots, underscores, and hyphens." >&2
    exit 2
fi

if [[ -z $database_uri && -z $postgrest_addresses && -z $dictionary_addresses && -z $translator_addresses && -z $atlas_username && -z $atlas_password ]]; then
    usage
    exit 2
fi

if [[ -n $atlas_username || -n $atlas_password ]]; then
    if ! command -v openssl >/dev/null 2>&1; then
        echo "OpenSSL is required to update Atlas credentials." >&2
        exit 1
    fi
    credentials_file="$nginx_dir/atlas.htpasswd"
    current_username=""
    if [[ -f $credentials_file ]]; then
        current_username=$(cut -d: -f1 "$credentials_file" | sed -n '1p')
    fi
    atlas_username=${atlas_username:-$current_username}
    if [[ -z $atlas_username ]]; then
        echo "A username is required when setting Atlas credentials." >&2
        exit 2
    fi
    if [[ -z $atlas_password ]]; then
        read -r -s -p "New Atlas password: " atlas_password
        printf '\n'
    fi
    if [[ -z $atlas_password ]]; then
        echo "Atlas password cannot be empty." >&2
        exit 2
    fi
    password_hash=$(openssl passwd -6 -stdin <<< "$atlas_password")
    credentials_temp=$(mktemp)
    printf '%s:%s\n' "$atlas_username" "$password_hash" > "$credentials_temp"
    install -m 0600 "$credentials_temp" "$credentials_file"
    rm -f "$credentials_temp"
    unset atlas_password password_hash
fi

write_upstreams() {
    local addresses=$1
    local destination=$2
    local temporary
    temporary=$(mktemp)
    ADDRESSES="$addresses" python3 - "$temporary" <<'PY'
import os
import sys
from urllib.parse import urlparse

addresses = [item.strip() for item in os.environ["ADDRESSES"].split(",") if item.strip()]
if not addresses:
    raise SystemExit("At least one service address is required")

servers = []
for address in addresses:
    parsed = urlparse(address if "://" in address else f"http://{address}")
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise SystemExit(f"Invalid service address: {address}")
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise SystemExit(f"Service addresses cannot contain paths, queries, or fragments: {address}")
    if parsed.scheme == "https":
        raise SystemExit(f"HTTPS upstreams require an Nginx TLS proxy configuration and are not supported: {address}")
    port = parsed.port or 80
    host = f"[{parsed.hostname}]" if ":" in parsed.hostname else parsed.hostname
    server = f"{host}:{port}"
    if server not in servers:
        servers.append(server)

with open(sys.argv[1], "w", encoding="ascii") as output:
    for server in servers:
        output.write(f"server {server};\n")
PY
    install -m 0644 "$temporary" "$destination"
    rm -f "$temporary"
}

if [[ -n $postgrest_addresses ]]; then
    write_upstreams "$postgrest_addresses" "$nginx_dir/postgrest-upstreams.conf"
fi
if [[ -n $dictionary_addresses ]]; then
    write_upstreams "$dictionary_addresses" "$nginx_dir/dictionary-service-upstreams.conf"
fi
if [[ -n $translator_addresses ]]; then
    write_upstreams "$translator_addresses" "$nginx_dir/entry-translator-upstreams.conf"
fi

database_label=""
if [[ -n $database_uri ]]; then
    DATABASE_URI="$database_uri" BOTJAGWAR_CONFIG="$botjagwar_config" POSTGREST_CONFIG_DIR="$postgrest_config_dir" python3 <<'PY'
import os
import re
from pathlib import Path
from urllib.parse import urlparse

database_uri = os.environ["DATABASE_URI"]
parsed = urlparse(database_uri)
if not parsed.scheme or any(character in database_uri for character in {'"', "\n", "\r"}):
    raise SystemExit("Invalid database URI")

path = Path(os.environ["BOTJAGWAR_CONFIG"])
content = path.read_text(encoding="utf-8")
updated, count = re.subn(
    r"(?m)^\s*database_uri\s*=.*$",
    f"database_uri = {database_uri}",
    content,
    count=1,
)
if count == 0:
    updated, count = re.subn(
        r"(?m)^\[global\]\s*$",
        f"[global]\ndatabase_uri = {database_uri}",
        content,
        count=1,
    )
if count != 1:
    raise SystemExit(f"Could not update database_uri in {path}")
path.write_text(updated, encoding="utf-8")

postgrest_dir = Path(os.environ["POSTGREST_CONFIG_DIR"])
for postgrest_path in postgrest_dir.glob("pgrest_*.ini"):
    content = postgrest_path.read_text(encoding="utf-8")
    updated, count = re.subn(
        r'(?m)^db-uri\s*=.*$',
        f'db-uri = "{database_uri}"',
        content,
        count=1,
    )
    if count != 1:
        raise SystemExit(f"Could not update db-uri in {postgrest_path}")
    postgrest_path.write_text(updated, encoding="utf-8")
PY
    database_label=$(DATABASE_URI="$database_uri" python3 <<'PY'
import os
from urllib.parse import urlparse

parsed = urlparse(os.environ["DATABASE_URI"])
host = parsed.hostname or "local database"
port = f":{parsed.port}" if parsed.port else ""
database = parsed.path.lstrip("/")
print(f"{host}{port}/{database}".rstrip("/"))
PY
)
fi

if [[ -z $database_label && -r $botjagwar_config ]]; then
    database_label=$(BOTJAGWAR_CONFIG="$botjagwar_config" python3 <<'PY'
import os
import re
from pathlib import Path

content = Path(os.environ["BOTJAGWAR_CONFIG"]).read_text(encoding="utf-8")
match = re.search(r"(?m)^\s*postgrest_backend_address\s*=\s*([^\s#;]+)", content)
print(f"{match.group(1).rstrip('/')}/botjagwar" if match else "")
PY
)
fi

DATABASE_LABEL="$database_label" RUNTIME_CONFIG="$runtime_config" python3 <<'PY'
import json
import os
from pathlib import Path

path = Path(os.environ["RUNTIME_CONFIG"])
try:
    config = json.loads(path.read_text(encoding="utf-8"))
except (FileNotFoundError, json.JSONDecodeError):
    config = {}
if os.environ["DATABASE_LABEL"]:
    config["databaseAddress"] = os.environ["DATABASE_LABEL"]
config.setdefault("postgrestAddresses", ["/api/database"])
config.setdefault("dictionaryServiceAddresses", ["/api/dictionary"])
config.setdefault("entryTranslatorAddresses", ["/api/translator"])
path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
PY

if [[ ! -r "/opt/botjagwar-certs/fullchain.pem" || ! -r "/opt/botjagwar-certs/privkey.pem" ]]; then
    echo "Atlas TLS certificate files are missing. Run $install_dir/setup-tls.sh first." >&2
    exit 1
fi
/usr/sbin/nginx -t -p "$install_dir/" -c "$nginx_config"
if [[ ${SKIP_SUPERVISOR_RESTART:-0} != 1 ]] && command -v supervisorctl >/dev/null 2>&1; then
    sudo supervisorctl restart botjagwar_atlas
fi

if [[ -n $database_uri ]]; then
    echo "Database configuration updated. Restart backend services separately when ready."
fi
echo "Atlas service addresses updated."
