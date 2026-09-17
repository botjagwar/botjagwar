#!/bin/bash

set -Eeuo pipefail

echo "Prepare versioned Botjagwar release"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python3 is not installed. Please install it manually."
  exit 1
fi
if ! python3 -m venv --help >/dev/null 2>&1; then
  echo "The Python venv module is not installed."
  exit 1
fi
if [[ -n ${TEST:-} && $TEST != 1 ]]; then
  echo "TEST must be unset for production or exactly 1 for an isolated test install." >&2
  exit 2
fi

src_dir=$(cd "$(dirname "$0")" && pwd)
opt_dir=${BOTJAGWAR_INSTALL_DIR:-/opt/botjagwar}
current_user=$(whoami)
current_group=$(id -gn)
POSTGREST_VERSION=${POSTGREST_VERSION:-11.2.1}
release_id=${BOTJAGWAR_RELEASE_ID:-$(date -u +%Y%m%dT%H%M%SZ)-$$}
if [[ ! $release_id =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]]; then
  echo "Invalid release identifier: $release_id" >&2
  exit 2
fi
releases_dir="$opt_dir/releases"
release_dir="$releases_dir/$release_id"
staging_dir="$release_dir"
legacy_release="$releases_dir/legacy-$release_id"
rendered_config_dir=$(mktemp -d)
rollback_dir=$(mktemp -d)

if [[ -n ${TEST:-} ]]; then
  config_dir=${BOTJAGWAR_CONFIG_DIR:-$opt_dir/shared/etc}
  state_dir=${BOTJAGWAR_STATE_DIR:-$opt_dir/shared/var}
else
  config_dir=${BOTJAGWAR_CONFIG_DIR:-/etc/botjagwar}
  state_dir=${BOTJAGWAR_STATE_DIR:-/var/lib/botjagwar}
  if [[ $opt_dir != /opt/botjagwar || $config_dir != /etc/botjagwar || $state_dir != /var/lib/botjagwar ]]; then
    echo "Custom deployment roots are supported only in TEST mode." >&2
    exit 2
  fi
fi

deployment_switched=0
previous_release=""
release_created=0
config_artifacts_created=0
supervisor_config_switched=0
ctranslate_config_switched=0
materialized_cron_switched=0
materialized_cron_had_previous=0
dashboard_cron_switched=0
dashboard_cron_had_previous=0
managed_links_switched=()
compatibility_paths=()
compatibility_targets=()
previous_running_programs=()

program_was_running() {
  local expected=$1 running_program
  for running_program in "${previous_running_programs[@]}"; do
    if [[ $running_program == "$expected" ]]; then
      return 0
    fi
  done
  return 1
}

running_program_matches_prefix() {
  local prefix=$1 running_program
  for running_program in "${previous_running_programs[@]}"; do
    if [[ $running_program == "$prefix"* ]]; then
      return 0
    fi
  done
  return 1
}

restore_managed_links() {
  local index name
  for ((index=${#managed_links_switched[@]} - 1; index >= 0; index--)); do
    name=${managed_links_switched[$index]}
    sudo rm -rf "$config_dir/$name" || return 1
    if [[ -e $rollback_dir/$name || -L $rollback_dir/$name ]]; then
      sudo mv "$rollback_dir/$name" "$config_dir/$name" || return 1
    fi
  done
  if [[ $supervisor_config_switched == 1 ]]; then
    sudo rm -f /etc/supervisor/conf.d/supervisor-botjagwar.conf || return 1
    if [[ -e $rollback_dir/supervisor-botjagwar.conf ]]; then
      sudo cp -a "$rollback_dir/supervisor-botjagwar.conf" \
        /etc/supervisor/conf.d/supervisor-botjagwar.conf || return 1
    fi
  fi
  if [[ $ctranslate_config_switched == 1 ]]; then
    sudo rm -f /etc/supervisor/conf.d/supervisor-ctranslate.conf || return 1
    if [[ -e $rollback_dir/supervisor-ctranslate.conf ]]; then
      sudo cp -a "$rollback_dir/supervisor-ctranslate.conf" \
        /etc/supervisor/conf.d/supervisor-ctranslate.conf || return 1
    fi
  fi
}

restore_compatibility_links() {
  local index path target
  for ((index=0; index < ${#compatibility_paths[@]}; index++)); do
    path=${compatibility_paths[$index]}
    target=${compatibility_targets[$index]}
    if [[ ! -e $path && ! -L $path ]]; then
      sudo ln -s "$target" "$path" || return 1
    fi
  done
}

restore_cron_file() {
  local cron_file=$1
  local backup_name=$2
  local had_previous=$3
  sudo rm -f "$cron_file" || return 1
  if [[ $had_previous == 1 ]]; then
    sudo cp -a "$rollback_dir/$backup_name" "$cron_file" || return 1
  fi
}

restore_scheduled_jobs() {
  if [[ $materialized_cron_switched == 1 ]]; then
    restore_cron_file \
      /etc/cron.d/botjagwar-materialized-views \
      botjagwar-materialized-views \
      "$materialized_cron_had_previous" || return 1
  fi
  if [[ $dashboard_cron_switched == 1 ]]; then
    restore_cron_file \
      /etc/cron.d/botjagwar-dashboard-statistics \
      botjagwar-dashboard-statistics \
      "$dashboard_cron_had_previous" || return 1
  fi
  sudo service cron restart || return 1
}

cleanup() {
  local status=$?
  local rollback_succeeded=1
  local current_target=""
  trap - EXIT
  if [[ $status != 0 && $deployment_switched == 1 ]]; then
    echo "Deployment failed after activation; restoring the previous release." >&2
    if [[ -n $previous_release ]]; then
      if ! sudo python3 "$src_dir/scripts/release_manager.py" --root "$opt_dir" rollback "$previous_release"; then
        rollback_succeeded=0
      fi
    elif [[ -d $legacy_release ]]; then
      if ! sudo python3 "$src_dir/scripts/release_manager.py" \
        --root "$opt_dir" rollback "releases/legacy-$release_id"; then
        rollback_succeeded=0
      fi
    else
      sudo rm -f "$opt_dir/current" || rollback_succeeded=0
    fi
    current_target=$(readlink -f "$opt_dir/current" 2>/dev/null || true)
    if [[ $current_target == "$release_dir" ]]; then
      rollback_succeeded=0
    fi
    if [[ $rollback_succeeded == 1 ]] && ! restore_compatibility_links; then
      rollback_succeeded=0
    fi
  fi
  if [[ $status != 0 && $rollback_succeeded == 1 && $config_artifacts_created == 1 ]]; then
    if ! restore_managed_links; then
      rollback_succeeded=0
    fi
    if [[ $rollback_succeeded == 1 && $deployment_switched == 1 \
      && -z ${TEST:-} && -z ${RESTART_ALL:-} ]]; then
      if ! rollback_managed_services; then
        rollback_succeeded=0
      fi
    fi
  fi
  if [[ $status != 0 \
    && ( $materialized_cron_switched == 1 || $dashboard_cron_switched == 1 ) ]]; then
    if ! restore_scheduled_jobs; then
      rollback_succeeded=0
    fi
  fi
  if [[ $status != 0 && $rollback_succeeded == 0 ]]; then
    echo "Automatic rollback failed; preserving release $release_dir for manual recovery." >&2
  elif [[ $status != 0 && $release_created == 1 ]]; then
    sudo rm -rf "$release_dir"
  fi
  if [[ $status != 0 && $rollback_succeeded == 1 && $config_artifacts_created == 1 ]]; then
    sudo rm -f "$config_dir/deployments/$release_id.ini" "$config_dir/haproxy-releases/$release_id.cfg"
    sudo rm -rf "$config_dir/pgrest-releases/$release_id"
  fi
  rm -rf "$rendered_config_dir" "$rollback_dir"
  exit "$status"
}
trap cleanup EXIT

sudo mkdir -p "$opt_dir"
sudo chown "$current_user":"$current_group" "$opt_dir"

exec 9>"$opt_dir/.install.lock"
if ! flock -n 9; then
  echo "Another Botjagwar installation is already running." >&2
  exit 1
fi

sudo mkdir -p "$releases_dir" "$config_dir" "$state_dir/user_data" "$state_dir/atlas/logs"
sudo chown "$current_user":"$current_group" "$releases_dir"

if [[ -z ${TEST:-} ]]; then
  if [[ ! -e /etc/botjagwar/supervisor-rpc-location.conf ]]; then
    legacy_rpc_location=/opt/botjagwar-front/config/nginx/supervisor-rpc-location.conf
    if [[ -s $legacy_rpc_location ]]; then
      sudo install -o root -g root -m 0644 "$legacy_rpc_location" /etc/botjagwar/supervisor-rpc-location.conf
    else
      sudo install -o root -g root -m 0644 /dev/null /etc/botjagwar/supervisor-rpc-location.conf
    fi
  fi
  if [[ ! -e /etc/botjagwar/supervisor-control.ini ]]; then
    sudo install -o "$current_user" -g "$current_group" -m 0600 /dev/null /etc/botjagwar/supervisor-control.ini
  fi
  if [[ ! -s /etc/botjagwar/supervisor-control-gateway.token ]]; then
    gateway_token=$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')
    printf '%s\n' "$gateway_token" | sudo tee /etc/botjagwar/supervisor-control-gateway.token >/dev/null
    unset gateway_token
  fi
  sudo chown "$current_user":"$current_group" /etc/botjagwar/supervisor-control.ini \
    /etc/botjagwar/supervisor-control-gateway.token
  sudo chmod 0600 /etc/botjagwar/supervisor-control.ini /etc/botjagwar/supervisor-control-gateway.token
  gateway_token=$(sudo cat /etc/botjagwar/supervisor-control-gateway.token)
  printf 'proxy_set_header X-Atlas-Gateway-Token "%s";\n' "$gateway_token" \
    | sudo tee /etc/botjagwar/supervisor-control-proxy.conf >/dev/null
  unset gateway_token
  sudo chown "$current_user":"$current_group" /etc/botjagwar/supervisor-control-proxy.conf
  sudo chmod 0600 /etc/botjagwar/supervisor-control-proxy.conf
fi

if [[ -e $release_dir || -e $staging_dir ]]; then
  echo "Release $release_id already exists." >&2
  exit 1
fi
mkdir -p "$staging_dir"
release_created=1

existing_supervisor_arguments=()
if [[ -z ${TEST:-} ]]; then
  for supervisor_config in \
    /etc/supervisor/conf.d/supervisor-botjagwar.conf \
    /etc/supervisor/conf.d/supervisor-ctranslate.conf; do
    if [[ -f $supervisor_config ]]; then
      existing_supervisor_arguments+=(--existing-supervisor-config "$supervisor_config")
    fi
  done
fi

existing_haproxy=""
for candidate in "$config_dir/haproxy.cfg" "$opt_dir/current/conf/haproxy.cfg" "$opt_dir/conf/haproxy.cfg"; do
  if [[ -f $candidate ]]; then
    existing_haproxy=$candidate
    break
  fi
done

render_arguments=(
  --template-dir "$src_dir/conf"
  --output-dir "$rendered_config_dir"
  --user "$current_user"
  --group "$current_group"
  --application-root "$opt_dir/current"
  --config-root "$config_dir"
  --state-root "$state_dir"
  --frontend-root "$opt_dir/current/frontend"
  --write-deployment-config "$rendered_config_dir/deployment.ini"
)
if [[ -f $config_dir/deployment.ini ]]; then
  render_arguments+=(--deployment-config "$config_dir/deployment.ini")
fi
if [[ -n $existing_haproxy ]]; then
  render_arguments+=(--existing-haproxy-config "$existing_haproxy")
fi
render_arguments+=("${existing_supervisor_arguments[@]}")
python3 "$src_dir/scripts/render_service_configs.py" "${render_arguments[@]}"

if [[ -z ${TEST:-} && -n ${TRANSLATOR_INSTANCES+x} \
  && ! -d /opt/ctranslate && ! -f /etc/supervisor/conf.d/supervisor-ctranslate.conf ]]; then
  echo "TRANSLATOR_INSTANCES requires an installed CTranslate deployment." >&2
  exit 1
fi

mapfile -t deployment_values < <(/usr/bin/python3 -c '
import configparser
import sys
parser = configparser.ConfigParser()
parser.read(sys.argv[1])
print(parser.get("deployment", "service_user"))
print(parser.get("deployment", "service_group"))
print(parser.getboolean("services", "autostart"))
print(parser.getint("deployment", "keep_releases"))
' "$rendered_config_dir/deployment.ini")
service_user=${deployment_values[0]}
service_group=${deployment_values[1]}
deployment_autostart=${deployment_values[2]}
keep_releases=${deployment_values[3]}
if [[ $service_user != "$current_user" || $service_group != "$current_group" ]]; then
  echo "Run the installer as the configured service identity $service_user:$service_group." >&2
  exit 1
fi
sudo chown -R "$service_user":"$service_group" "$state_dir"
sudo chmod 0700 "$state_dir"

managed_programs=()
opt_in_programs=()
collect_rendered_programs() {
  local config_file=$1 line program="" program_autostart=""
  while IFS= read -r line; do
    if [[ $line =~ ^\[program:([^]]+)\]$ ]]; then
      if [[ -n $program && $program_autostart == true ]]; then
        managed_programs+=("$program")
      elif [[ -n $program && $program_autostart == false ]]; then
        opt_in_programs+=("$program")
      fi
      program=${BASH_REMATCH[1]}
      program_autostart=""
    elif [[ -n $program && $line =~ ^autostart=(true|false)$ ]]; then
      program_autostart=${BASH_REMATCH[1]}
    fi
  done < "$config_file"
  if [[ -n $program && $program_autostart == true ]]; then
    managed_programs+=("$program")
  elif [[ -n $program && $program_autostart == false ]]; then
    opt_in_programs+=("$program")
  fi
}
collect_rendered_programs "$rendered_config_dir/supervisor-botjagwar.conf"
if [[ -d /opt/ctranslate || -f /etc/supervisor/conf.d/supervisor-ctranslate.conf ]]; then
  collect_rendered_programs "$rendered_config_dir/supervisor-ctranslate.conf"
fi

restart_managed_services() {
  if (( ${#managed_programs[@]} > 0 )); then
    sudo supervisorctl restart "${managed_programs[@]}"
  fi
}

healthcheck_managed_services() {
  local atlas_status attempt program status
  for attempt in $(seq 1 30); do
    status=0
    for program in "${managed_programs[@]}"; do
      if ! sudo supervisorctl status "$program" | grep -q 'RUNNING'; then
        status=1
        break
      fi
    done
    if [[ $status == 0 ]]; then
      if [[ $deployment_autostart != True ]]; then
        return 0
      fi
      atlas_status=$(curl --insecure --silent --output /dev/null --write-out '%{http_code}' \
        https://127.0.0.1:38000/ || true)
      if curl --fail --silent --show-error http://127.0.0.1:8000/health >/dev/null \
        && curl --fail --silent --show-error http://127.0.0.1:8001/ping >/dev/null \
        && curl --fail --silent --show-error http://127.0.0.1:8004/health >/dev/null \
        && curl --fail --silent --show-error http://127.0.0.1:8100/ >/dev/null \
        && [[ $atlas_status == 401 ]]; then
        return 0
      fi
    fi
    sleep 1
  done
  echo "Managed services did not become healthy within 30 seconds." >&2
  return 1
}

rollback_managed_services() {
  local attempt config_file expected_running line program status
  local rollback_programs=()
  sudo supervisorctl reread || return 1
  sudo supervisorctl update || return 1
  for config_file in \
    "$rollback_dir/supervisor-botjagwar.conf" \
    "$rollback_dir/supervisor-ctranslate.conf"; do
    if [[ ! -f $config_file ]]; then
      continue
    fi
    while IFS= read -r line; do
      if [[ $line =~ ^\[program:([^]]+)\]$ ]]; then
        rollback_programs+=("${BASH_REMATCH[1]}")
      fi
    done < "$config_file"
  done
  if (( ${#rollback_programs[@]} == 0 )); then
    return 0
  fi
  for program in "${rollback_programs[@]}"; do
    expected_running=0
    program_was_running "$program" && expected_running=1
    if [[ $expected_running == 1 ]]; then
      sudo supervisorctl restart "$program" || return 1
    else
      sudo supervisorctl stop "$program" >/dev/null 2>&1 || true
    fi
  done
  for attempt in $(seq 1 30); do
    status=0
    for program in "${rollback_programs[@]}"; do
      expected_running=0
      program_was_running "$program" && expected_running=1
      if sudo supervisorctl status "$program" | grep -q 'RUNNING'; then
        [[ $expected_running == 1 ]] || status=1
      elif [[ $expected_running == 1 ]]; then
        status=1
      fi
    done
    if [[ $status == 0 ]] && program_was_running load_balancer; then
      if running_program_matches_prefix entry_translator_ \
        && ! curl --fail --silent http://127.0.0.1:8000/health >/dev/null; then
        status=1
      fi
      if running_program_matches_prefix dictionary_service_ \
        && ! curl --fail --silent http://127.0.0.1:8001/ping >/dev/null; then
        status=1
      fi
      if running_program_matches_prefix postgrest_ \
        && ! curl --fail --silent http://127.0.0.1:8100/ >/dev/null; then
        status=1
      fi
    fi
    if [[ $status == 0 ]] && program_was_running tenymalagasy_mirror \
      && ! curl --fail --silent http://127.0.0.1:8004/health >/dev/null; then
      status=1
    fi
    if [[ $status == 0 ]]; then
      return 0
    fi
    sleep 1
  done
  return 1
}

python3 -m venv "$staging_dir/pyenv"
source "$staging_dir/pyenv/bin/activate"
export UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/botjagwar-uv-cache}"
if ! command -v uv >/dev/null 2>&1; then
  python -m pip install uv
fi
uv pip install -r "$src_dir/requirements.txt"

cp -R "$src_dir/api" "$src_dir/data" "$src_dir/scripts" "$staging_dir/"
mkdir -p "$staging_dir/conf"
shopt -s dotglob nullglob
for conf_entry in "$src_dir/conf"/*; do
  if [[ ${conf_entry##*/} != config.ini ]]; then
    cp -R "$conf_entry" "$staging_dir/conf/"
  fi
done
shopt -u dotglob nullglob
cp "$src_dir"/*.py "$staging_dir/"
mkdir -p "$staging_dir/bin"
install_postgrest() {
  local source_path=$1
  local binary_path=$2
  if [[ -x $source_path ]]; then
    install -m 0755 "$source_path" "$binary_path"
    return 0
  fi
  local architecture asset_name download_dir download_url
  architecture=$(uname -m)
  case "$architecture" in
    x86_64|amd64) asset_name="postgrest-v${POSTGREST_VERSION}-linux-static-x64.tar.xz" ;;
    aarch64|arm64) asset_name="postgrest-v${POSTGREST_VERSION}-ubuntu-aarch64.tar.xz" ;;
    *)
      echo "No postgrest binary for architecture $architecture." >&2
      return 1
      ;;
  esac
  download_dir=$(mktemp -d)
  download_url="https://github.com/PostgREST/postgrest/releases/download/v${POSTGREST_VERSION}/${asset_name}"
  if curl --fail --location --silent --show-error --output "$download_dir/postgrest.tar.xz" "$download_url" \
    && tar -xJf "$download_dir/postgrest.tar.xz" -C "$download_dir" \
    && install -m 0755 "$download_dir/postgrest" "$binary_path"; then
    rm -rf "$download_dir"
    echo "Downloaded PostgREST v${POSTGREST_VERSION} ($architecture) from GitHub releases."
    return 0
  fi
  rm -rf "$download_dir"
  echo "Could not download PostgREST v${POSTGREST_VERSION} from $download_url." >&2
  return 1
}
if ! install_postgrest "$src_dir/bin/postgrest" "$staging_dir/bin/postgrest"; then
  echo "No usable postgrest binary. Place one at $src_dir/bin/postgrest or allow network access." >&2
  exit 1
fi
install -m 0755 "$src_dir/scripts/configure-atlas-supervisor" "$staging_dir/bin/configure-atlas-supervisor"

if [[ ! -f $config_dir/config.ini ]]; then
  config_candidates=("$opt_dir/current/conf/config.ini" "$opt_dir/conf/config.ini")
  if [[ -n ${TEST:-} ]]; then
    config_candidates+=("$src_dir/conf/test_config.ini")
  else
    config_candidates+=("$src_dir/conf/config.ini")
  fi
  for candidate in "${config_candidates[@]}"; do
    if [[ -f $candidate ]]; then
      sudo install -o "$current_user" -g "$current_group" -m 0600 "$candidate" "$config_dir/config.ini"
      break
    fi
  done
fi
if [[ ! -f $config_dir/config.ini ]]; then
  echo "No config.ini was found. Create $config_dir/config.ini before installing." >&2
  exit 1
fi
if [[ -L $config_dir/config.ini ]]; then
  echo "$config_dir/config.ini must be a regular protected file, not a symbolic link." >&2
  exit 1
fi
sudo chown "$current_user:$current_group" "$config_dir/config.ini"
sudo chmod 0600 "$config_dir/config.ini"
if ! /usr/bin/python3 "$src_dir/scripts/validate_config.py" "$config_dir/config.ini"; then
  echo "Botjagwar configuration is invalid." >&2
  exit 1
fi

if [[ ! -e $state_dir/user_data/.state-migrated ]]; then
  for candidate in "$opt_dir/current/user_data" "$opt_dir/user_data"; do
    if [[ -d $candidate && ! -L $candidate ]]; then
      cp -a "$candidate/." "$state_dir/user_data/"
      break
    fi
  done
  touch "$state_dir/user_data/.state-migrated"
fi
install -m 0644 "$src_dir/user_data/basic_english.txt" "$state_dir/user_data/basic_english.txt"

rm -f "$staging_dir/conf/haproxy.cfg"
rm -rf "$staging_dir/conf/pgrest"
ln -s "$config_dir/config.ini" "$staging_dir/conf/config.ini"
ln -s "$config_dir/haproxy.cfg" "$staging_dir/conf/haproxy.cfg"
ln -s "$config_dir/pgrest" "$staging_dir/conf/pgrest"
ln -s "$state_dir/user_data" "$staging_dir/user_data"

python3 "$src_dir/scripts/sync_postgrest_database_uri.py" \
  "$config_dir/config.ini" \
  "$rendered_config_dir/pgrest"

if [[ -z ${TEST:-} ]]; then
  sudo apt-get install -y haproxy redis-server supervisor nginx cron
  ATLAS_INSTALL_DIR="$staging_dir/frontend" \
    ATLAS_CONFIG_DIR="$config_dir/nginx" \
    ATLAS_STATE_DIR="$state_dir/atlas" \
    ATLAS_STAGE_ONLY=1 \
    BOTJAGWAR_CONFIG="$config_dir/config.ini" \
    bash "$src_dir/frontend/install.sh"
  certificate_dir=${ATLAS_CERTIFICATE_DIR:-/opt/botjagwar-certs}
  if [[ ! -r $certificate_dir/fullchain.pem || ! -r $certificate_dir/privkey.pem ]]; then
    ATLAS_INSTALL_DIR="$staging_dir/frontend" \
      ATLAS_CERTIFICATE_DIR="$certificate_dir" \
      bash "$src_dir/frontend/setup-tls.sh"
  fi
fi

"$staging_dir/pyenv/bin/python" -m compileall -q "$staging_dir/api" "$staging_dir/scripts" "$staging_dir"/*.py
test -x "$staging_dir/bin/postgrest"
test -x "$staging_dir/bin/configure-atlas-supervisor"
if [[ -z ${TEST:-} ]]; then
  sudo /usr/sbin/haproxy -c -f "$rendered_config_dir/haproxy.cfg"
  if [[ -d $staging_dir/frontend ]]; then
    /usr/sbin/nginx -t -p "$staging_dir/frontend/" -c "$staging_dir/frontend/config/nginx/nginx.conf"
  fi
  if [[ -n ${BOTJAGWAR_DASHBOARD_STATISTICS_SOURCE:-} ]]; then
    BOTJAGWAR_DASHBOARD_STATISTICS_SOURCE="$BOTJAGWAR_DASHBOARD_STATISTICS_SOURCE" \
      BOTJAGWAR_ATLAS_STATE_DIR="$state_dir/atlas" \
      "$staging_dir/pyenv/bin/python" "$staging_dir/scripts/fetch_dashboard_statistics.py"
  else
    BOTJAGWAR_CONFIG="$config_dir/config.ini" \
      BOTJAGWAR_ATLAS_STATE_DIR="$state_dir/atlas" \
      "$staging_dir/pyenv/bin/python" "$staging_dir/scripts/refresh_dashboard_statistics.py"
    BOTJAGWAR_CONFIG="$config_dir/config.ini" \
      "$staging_dir/pyenv/bin/python" "$staging_dir/scripts/snapshot_page_check_statistics.py" \
      --check-storage
  fi
fi
touch "$release_dir/.release-complete"

deactivate

legacy_prepared=0
if [[ ! -L $opt_dir/current && -d $opt_dir/pyenv ]]; then
  sudo mkdir -p "$legacy_release"
  for legacy_name in api bin conf data pyenv scripts user_data; do
    if [[ -e $opt_dir/$legacy_name && ! -L $opt_dir/$legacy_name ]]; then
      sudo cp -a "$opt_dir/$legacy_name" "$legacy_release/$legacy_name"
    fi
  done
  for legacy_script in "$opt_dir"/*.py; do
    if [[ -f $legacy_script && ! -L $legacy_script ]]; then
      sudo cp -a "$legacy_script" "$legacy_release/"
    fi
  done
  if [[ -z ${TEST:-} && -d /opt/botjagwar-front && ! -L /opt/botjagwar-front ]]; then
    sudo cp -a /opt/botjagwar-front "$legacy_release/frontend"
  fi
  sudo touch "$legacy_release/.release-complete"
  legacy_prepared=1
fi

sudo mkdir -p "$config_dir/deployments" "$config_dir/haproxy-releases" "$config_dir/pgrest-releases"
config_artifacts_created=1
sudo chown "$service_user":"$service_group" \
  "$config_dir/deployments" "$config_dir/haproxy-releases" "$config_dir/pgrest-releases"
sudo install -o "$service_user" -g "$service_group" -m 0600 \
  "$rendered_config_dir/deployment.ini" "$config_dir/deployments/$release_id.ini"
sudo install -o "$service_user" -g "$service_group" -m 0640 \
  "$rendered_config_dir/haproxy.cfg" "$config_dir/haproxy-releases/$release_id.cfg"
sudo cp -a "$rendered_config_dir/pgrest" "$config_dir/pgrest-releases/$release_id"
sudo chown -R "$service_user":"$service_group" "$config_dir/pgrest-releases/$release_id"
sudo chmod 0750 "$config_dir/pgrest-releases/$release_id"
sudo chmod 0600 "$config_dir/pgrest-releases/$release_id"/pgrest_*.ini

switch_managed_link() {
  local name=$1
  local target=$2
  local temporary="$config_dir/.$name.$release_id"
  if [[ -e $config_dir/$name || -L $config_dir/$name ]]; then
    sudo mv "$config_dir/$name" "$rollback_dir/$name"
  fi
  managed_links_switched+=("$name")
  sudo ln -s "$target" "$temporary"
  sudo mv -Tf "$temporary" "$config_dir/$name"
}

switch_managed_link deployment.ini "deployments/$release_id.ini"
switch_managed_link haproxy.cfg "haproxy-releases/$release_id.cfg"
switch_managed_link pgrest "pgrest-releases/$release_id"

if [[ -z ${TEST:-} ]]; then
  for config_file in \
    /etc/supervisor/conf.d/supervisor-botjagwar.conf \
    /etc/supervisor/conf.d/supervisor-ctranslate.conf; do
    if [[ ! -f $config_file ]]; then
      continue
    fi
    sudo cp -a "$config_file" "$rollback_dir/${config_file##*/}"
    while IFS= read -r line; do
      if [[ $line =~ ^\[program:([^]]+)\]$ ]]; then
        program=${BASH_REMATCH[1]}
        if sudo supervisorctl status "$program" | grep -q 'RUNNING'; then
          previous_running_programs+=("$program")
        fi
      fi
    done < "$config_file"
  done
fi
for program in "${opt_in_programs[@]}"; do
  if program_was_running "$program"; then
    managed_programs+=("$program")
  fi
done
if [[ -z ${TEST:-} ]]; then
  supervisor_config_switched=1
  sudo install -o root -g root -m 0644 \
    "$rendered_config_dir/supervisor-botjagwar.conf" \
    /etc/supervisor/conf.d/supervisor-botjagwar.conf
  if [[ -d /opt/ctranslate || -f /etc/supervisor/conf.d/supervisor-ctranslate.conf ]]; then
    ctranslate_config_switched=1
    sudo install -o root -g root -m 0644 \
      "$rendered_config_dir/supervisor-ctranslate.conf" \
      /etc/supervisor/conf.d/supervisor-ctranslate.conf
  fi
fi

previous_release=$(sudo python3 "$src_dir/scripts/release_manager.py" --root "$opt_dir" activate "$release_id")
if [[ -z $previous_release && $legacy_prepared == 1 ]]; then
  previous_release="releases/legacy-$release_id"
fi
deployment_switched=1

for legacy_name in api bin conf data pyenv scripts user_data; do
  if [[ -e $opt_dir/$legacy_name && ! -L $opt_dir/$legacy_name ]]; then
    compatibility_paths+=("$opt_dir/$legacy_name")
    if [[ $legacy_name == user_data ]]; then
      compatibility_targets+=("$state_dir/user_data")
    else
      compatibility_targets+=("current/$legacy_name")
    fi
    if [[ $legacy_prepared == 1 ]]; then
      if [[ $legacy_name == user_data ]]; then
        sudo cp -a "$opt_dir/user_data/." "$state_dir/user_data/"
      fi
      sudo rm -rf "$opt_dir/$legacy_name"
    else
      sudo mkdir -p "$legacy_release"
      sudo mv "$opt_dir/$legacy_name" "$legacy_release/$legacy_name"
    fi
  fi
  if [[ ! -e $opt_dir/$legacy_name && ! -L $opt_dir/$legacy_name ]]; then
    if [[ $legacy_name == user_data ]]; then
      sudo ln -s "$state_dir/user_data" "$opt_dir/user_data"
    else
      sudo ln -s "current/$legacy_name" "$opt_dir/$legacy_name"
    fi
  fi
done
for installed_script in "$release_dir"/*.py; do
  script_name=$(basename "$installed_script")
  if [[ -e $opt_dir/$script_name && ! -L $opt_dir/$script_name ]]; then
    compatibility_paths+=("$opt_dir/$script_name")
    compatibility_targets+=("current/$script_name")
    if [[ $legacy_prepared == 1 ]]; then
      sudo rm -f "$opt_dir/$script_name"
    else
      sudo mkdir -p "$legacy_release"
      sudo mv "$opt_dir/$script_name" "$legacy_release/$script_name"
    fi
  fi
  if [[ ! -e $opt_dir/$script_name && ! -L $opt_dir/$script_name ]]; then
    sudo ln -s "current/$script_name" "$opt_dir/$script_name"
  fi
done
if [[ -z ${TEST:-} ]]; then
  if [[ -d /opt/botjagwar-front && ! -L /opt/botjagwar-front ]]; then
    compatibility_paths+=("/opt/botjagwar-front")
    compatibility_targets+=("$opt_dir/current/frontend")
    if [[ $legacy_prepared == 1 ]]; then
      sudo rm -rf /opt/botjagwar-front
    else
      sudo mkdir -p "$legacy_release"
      sudo mv /opt/botjagwar-front "$legacy_release/frontend"
    fi
  fi
  if [[ ! -e /opt/botjagwar-front && ! -L /opt/botjagwar-front ]]; then
    sudo ln -s "$opt_dir/current/frontend" /opt/botjagwar-front
  fi
fi

if [[ -z ${TEST:-} ]]; then
  materialized_cron_file=/etc/cron.d/botjagwar-materialized-views
  materialized_cron_source="$rendered_config_dir/botjagwar-materialized-views"
  printf '%s\n' \
    'SHELL=/bin/bash' \
    'PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin' \
    "45 0,12 * * * $current_user $opt_dir/current/pyenv/bin/python $opt_dir/current/scripts/refresh_materialized_views.py >> $state_dir/user_data/materialized_view_refresh.log 2>&1" \
    > "$materialized_cron_source"
  if [[ -e $materialized_cron_file || -L $materialized_cron_file ]]; then
    sudo cp -a "$materialized_cron_file" "$rollback_dir/botjagwar-materialized-views"
    materialized_cron_had_previous=1
  fi
  materialized_cron_switched=1
  sudo install -o root -g root -m 0644 "$materialized_cron_source" "$materialized_cron_file"

  dashboard_cron_file=/etc/cron.d/botjagwar-dashboard-statistics
  dashboard_cron_source="$rendered_config_dir/botjagwar-dashboard-statistics"
  if [[ -n ${BOTJAGWAR_DASHBOARD_STATISTICS_SOURCE:-} ]]; then
    printf '%s\n' \
      'SHELL=/bin/bash' \
      'PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin' \
      "*/5 * * * * $current_user BOTJAGWAR_DASHBOARD_STATISTICS_SOURCE=$BOTJAGWAR_DASHBOARD_STATISTICS_SOURCE $opt_dir/current/pyenv/bin/python $opt_dir/current/scripts/fetch_dashboard_statistics.py >> $state_dir/user_data/dashboard_statistics_refresh.log 2>&1" \
      > "$dashboard_cron_source"
  else
    printf '%s\n' \
      'SHELL=/bin/bash' \
      'PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin' \
      "*/5 * * * * $current_user $opt_dir/current/pyenv/bin/python $opt_dir/current/scripts/refresh_atlas_dashboard_statistics_mv.py >> $state_dir/user_data/materialized_view_refresh.log 2>&1" \
      "*/5 * * * * $current_user $opt_dir/current/pyenv/bin/python $opt_dir/current/scripts/refresh_dashboard_statistics.py >> $state_dir/user_data/dashboard_statistics_refresh.log 2>&1" \
      "*/5 * * * * $current_user BOTJAGWAR_CONFIG=$config_dir/config.ini $opt_dir/current/pyenv/bin/python $opt_dir/current/scripts/snapshot_page_check_statistics.py >> $state_dir/user_data/page_check_statistics_snapshot.log 2>&1" \
      > "$dashboard_cron_source"
  fi
  if [[ -e $dashboard_cron_file || -L $dashboard_cron_file ]]; then
    sudo cp -a "$dashboard_cron_file" "$rollback_dir/botjagwar-dashboard-statistics"
    dashboard_cron_had_previous=1
  fi
  dashboard_cron_switched=1
  sudo install -o root -g root -m 0644 "$dashboard_cron_source" "$dashboard_cron_file"
  sudo service cron restart
fi

if [[ -z ${TEST:-} && -z ${RESTART_ALL:-} ]]; then
  sudo supervisorctl reread
  sudo supervisorctl update
  restart_managed_services
  healthcheck_managed_services
fi

prune_arguments=(--root "$opt_dir" --config-root "$config_dir")
if [[ -n $previous_release ]]; then
  prune_arguments+=(--protect "${previous_release#releases/}")
fi
sudo python3 "$src_dir/scripts/release_manager.py" "${prune_arguments[@]}" prune --keep "$keep_releases"

deployment_switched=0
release_created=0
config_artifacts_created=0
rm -rf "$rendered_config_dir" "$rollback_dir"
trap - EXIT

echo "Botjagwar release $release_id is active at $opt_dir/current"

if [[ -n ${INSTALL_PG:-} ]]; then
  echo "Automatic PostgreSQL installation/configuration is currently not supported."
fi
