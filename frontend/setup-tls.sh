#!/bin/bash
set -euo pipefail

install_dir=${ATLAS_INSTALL_DIR:-/opt/botjagwar/current/frontend}
certificate_dir=${ATLAS_CERTIFICATE_DIR:-/opt/botjagwar-certs}
domain=${ATLAS_DOMAIN:-}
email=${ATLAS_CERTBOT_EMAIL:-${CERTBOT_EMAIL:-}}
current_user=$(whoami)
current_group=$(id -gn)
webroot=/var/www/botjagwar-certbot
site_available=/etc/nginx/sites-available/botjagwar-atlas
site_enabled=/etc/nginx/sites-enabled/botjagwar-atlas
deploy_hook=/etc/letsencrypt/renewal-hooks/deploy/botjagwar-atlas

usage() {
    printf '%s\n' \
        "Usage: setup-tls.sh --domain DOMAIN" \
        "" \
        "Options:" \
        "  --domain DOMAIN  DNS hostname (or set ATLAS_DOMAIN)" \
        "  --help           Show this help"
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --domain)
            domain=${2:?Missing value for --domain}
            shift 2
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

if [[ -z $domain ]]; then
    echo "Set ATLAS_DOMAIN or pass --domain with the Atlas DNS hostname." >&2
    exit 2
fi

domain=${domain,,}
if [[ ! $domain =~ ^([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$ || ${#domain} -gt 253 ]]; then
    echo "Domain is not a valid DNS hostname." >&2
    exit 2
fi

sudo apt-get update
sudo apt-get install -y certbot nginx
sudo mkdir -p "$webroot/.well-known/acme-challenge" "$certificate_dir"

sudo tee "$site_available" >/dev/null <<EOF
server {
    listen 80;
    listen [::]:80;
    server_name $domain;

    location ^~ /.well-known/acme-challenge/ {
        root $webroot;
        default_type text/plain;
        try_files \$uri =404;
    }

    location / {
        return 301 https://$domain:38000\$request_uri;
    }
}
EOF
sudo ln -sfn "$site_available" "$site_enabled"
sudo /usr/sbin/nginx -t
sudo systemctl reload nginx

certbot_arguments=(
    certonly
    --webroot
    --webroot-path "$webroot"
    --cert-name "$domain"
    --domain "$domain"
    --non-interactive
    --agree-tos
    --keep-until-expiring
    --preferred-challenges http
)
if [[ -n $email ]]; then
    certbot_arguments+=(--email "$email")
else
    certbot_arguments+=(--register-unsafely-without-email)
fi
if ! sudo test -r "/etc/letsencrypt/live/$domain/fullchain.pem" || ! sudo test -r "/etc/letsencrypt/live/$domain/privkey.pem"; then
    sudo /usr/bin/certbot "${certbot_arguments[@]}"
else
    echo "Reusing the existing Certbot certificate for $domain."
fi

sudo install -m 0644 "/etc/letsencrypt/live/$domain/fullchain.pem" "$certificate_dir/fullchain.pem"
sudo install -m 0600 "/etc/letsencrypt/live/$domain/privkey.pem" "$certificate_dir/privkey.pem"
printf '%s\n' "$domain" | sudo tee "$certificate_dir/domain" >/dev/null
sudo chown -R "$current_user:$current_group" "$certificate_dir"

sudo mkdir -p /etc/letsencrypt/renewal-hooks/deploy
sudo tee "$deploy_hook" >/dev/null <<'EOF'
#!/bin/bash
set -euo pipefail

install_dir=/opt/botjagwar/current/frontend
certificate_dir=/opt/botjagwar-certs
domain=$(<"$certificate_dir/domain")
owner=$(stat -c %U "$certificate_dir")
group=$(stat -c %G "$certificate_dir")

install -m 0644 "/etc/letsencrypt/live/$domain/fullchain.pem" "$certificate_dir/fullchain.pem"
install -m 0600 "/etc/letsencrypt/live/$domain/privkey.pem" "$certificate_dir/privkey.pem"
chown "$owner:$group" "$certificate_dir/fullchain.pem" "$certificate_dir/privkey.pem"
/usr/sbin/nginx -t -p "$install_dir/" -c "$install_dir/config/nginx/nginx.conf"
if /usr/bin/supervisorctl status botjagwar_atlas >/dev/null 2>&1; then
    /usr/bin/supervisorctl restart botjagwar_atlas
fi
EOF
sudo chmod 0755 "$deploy_hook"

# Keep existing lineages for the selected hostname renewable through the same
# webroot instead of letting stale standalone settings break global renewals.
sudo python3 - "$webroot" "$domain" <<'PY'
import re
import sys
from pathlib import Path

webroot = sys.argv[1]
domain = sys.argv[2]
renewal_dir = Path("/etc/letsencrypt/renewal")
for path in renewal_dir.glob("*.conf"):
    if path.stem != domain and not path.stem.startswith(f"{domain}-"):
        continue
    content = path.read_text(encoding="utf-8")
    content, count = re.subn(r"(?m)^authenticator\s*=.*$", "authenticator = webroot", content, count=1)
    if count != 1:
        continue
    if re.search(r"(?m)^webroot_path\s*=", content):
        content = re.sub(r"(?m)^webroot_path\s*=.*$", f"webroot_path = {webroot},", content, count=1)
    else:
        content = re.sub(
            r"(?m)^authenticator\s*=\s*webroot\s*$",
            f"authenticator = webroot\nwebroot_path = {webroot},",
            content,
            count=1,
        )
    path.write_text(content, encoding="utf-8")
PY

if systemctl list-unit-files certbot.timer >/dev/null 2>&1; then
    sudo systemctl enable --now certbot.timer
else
    sudo tee /etc/cron.d/certbot >/dev/null <<'EOF'
SHELL=/bin/sh
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
17 2,14 * * * root certbot renew --quiet
EOF
    sudo chmod 0644 /etc/cron.d/certbot
fi

echo "Atlas TLS certificate installed for $domain."
