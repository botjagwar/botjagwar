#!/bin/bash

set -Eeuo pipefail

src_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
opt_dir_ctranslate=/opt/ctranslate
model_source=${CTRANSLATE_MODEL_DIR:-$HOME/nllb-200-3.3B-int8}
rendered_config_dir=$(mktemp -d)
trap 'rm -rf "$rendered_config_dir"' EXIT

if [[ ! -d $model_source ]]; then
  echo "Place an int8 CTranslate2 NLLB model in $model_source or set CTRANSLATE_MODEL_DIR." >&2
  exit 1
fi
python3 "$src_dir/scripts/render_service_configs.py" \
  --template-dir "$src_dir/conf" \
  --output-dir "$rendered_config_dir" \
  --user "$(whoami)"

echo "Installing ctranslate for NLLB"
if [[ -d $opt_dir_ctranslate ]]; then
  sudo rm -rf "$opt_dir_ctranslate"
fi
sudo mkdir -p "$opt_dir_ctranslate"
sudo chown "$(whoami):$(id -gn)" -R "$opt_dir_ctranslate"
cp "$src_dir/ctranslate.py" "$opt_dir_ctranslate"
cp "$src_dir/ctranslate-lite.py" "$opt_dir_ctranslate"
cp -r "$src_dir/api" "$opt_dir_ctranslate"

cd "$opt_dir_ctranslate"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python3 is not installed."
  exit 1
fi
if ! python3 -m venv --help >/dev/null 2>&1; then
  echo "The Python venv module is not installed."
  exit 1
fi

python3 -m venv venv
source venv/bin/activate
python3 -m pip install uv
python3 -m uv pip install -r "$src_dir/requirements-ctranslate.txt"
cp -r "$model_source" "$opt_dir_ctranslate/nllb-200-3.3B-int8"

if [[ -z ${TEST:-} ]]; then
  # Install dependencies if NOT in test mode
  # this should allow for an increase of the speed-up regarding build time and is not needed
  # anyway by the unit tests when in testing mode
  sudo apt-get install -y haproxy
  sudo apt-get install -y redis-server
  sudo mkdir -p "$opt_dir_ctranslate/conf"
  sudo cp "$rendered_config_dir/haproxy.cfg" "$opt_dir_ctranslate/conf/"
  sudo apt-get install -y supervisor

  if [[ -d /etc/supervisor/conf.d ]]; then
    sudo cp "$rendered_config_dir/supervisor-ctranslate.conf" /etc/supervisor/conf.d/supervisor-ctranslate.conf
  fi
  if [[ -z ${RESTART_ALL:-} ]]; then
    echo "Supervisor installation is complete. Reloading config"
    sudo supervisorctl reload
  fi
fi
