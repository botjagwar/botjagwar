#!/bin/bash

set -euo pipefail

src_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
model_source=${GEMMA_SOURCE_DIR:-$HOME/gemma-4-E2B-it-GGUF/gemma-4-E2B-it-Q4_K_M.gguf}
install_root=${GEMMA_INSTALL_DIR:-/opt/gemma}

if [[ -n ${TEST:-} && ( $install_root == /opt/gemma || $install_root == /opt/gemma/* ) ]]; then
  echo "TEST mode requires GEMMA_INSTALL_DIR outside /opt/gemma." >&2
  exit 1
fi

if [[ ! -f $model_source || $model_source != *.gguf ]]; then
  echo "Invalid Gemma source: $model_source must be a local GGUF model file." >&2
  exit 1
fi

parent_dir=$(dirname "$install_root")
stage_root="$parent_dir/.gemma-stage-$$"
backup_root="$parent_dir/.gemma-backup-$$"
rendered_config_dir=$(mktemp -d)
activated=0

cleanup() {
  status=$?
  rm -rf "$rendered_config_dir"
  if [[ -n ${TEST:-} ]]; then
    rm -rf "$stage_root"
  else
    sudo rm -rf "$stage_root"
  fi
  if [[ $status != 0 && $activated == 1 ]]; then
    if [[ -n ${TEST:-} ]]; then
      rm -rf "$install_root"
      [[ ! -e $backup_root ]] || mv "$backup_root" "$install_root"
    else
      sudo rm -rf "$install_root"
      [[ ! -e $backup_root ]] || sudo mv "$backup_root" "$install_root"
    fi
  fi
  exit "$status"
}
trap cleanup EXIT

python3 "$src_dir/scripts/render_service_configs.py" \
  --gemma-only \
  --template-dir "$src_dir/conf" \
  --output-dir "$rendered_config_dir" \
  --gemma-root "$install_root" \
  --user "$(whoami)"

if [[ -n ${TEST:-} ]]; then
  mkdir -p "$parent_dir"
  rm -rf "$stage_root" "$backup_root"
  mkdir -p "$stage_root"
else
  sudo mkdir -p "$parent_dir"
  sudo rm -rf "$stage_root" "$backup_root"
  sudo mkdir -p "$stage_root"
  sudo chown "$(whoami):$(id -gn)" "$stage_root"
fi

cp "$src_dir/gemma_service.py" "$stage_root/"
cp "$src_dir/requirements-gemma.txt" "$stage_root/"
mkdir "$stage_root/model"
cp "$model_source" "$stage_root/model/model.gguf"
python3 -m venv "$stage_root/venv"
if [[ ${GEMMA_SKIP_DEPENDENCIES:-0} != 1 ]]; then
  "$stage_root/venv/bin/python" -m pip install --upgrade pip
  CMAKE_ARGS=${GEMMA_CMAKE_ARGS:--DGGML_CUDA=on} \
    "$stage_root/venv/bin/python" -m pip install -r "$stage_root/requirements-gemma.txt"
elif [[ -z ${TEST:-} ]]; then
  echo "GEMMA_SKIP_DEPENDENCIES is only permitted in TEST mode." >&2
  exit 1
fi
"$stage_root/venv/bin/python" -m py_compile "$stage_root/gemma_service.py"

if [[ -n ${TEST:-} ]]; then
  [[ ! -e $install_root ]] || mv "$install_root" "$backup_root"
  mv "$stage_root" "$install_root"
else
  [[ ! -e $install_root ]] || sudo mv "$install_root" "$backup_root"
  sudo mv "$stage_root" "$install_root"
fi
activated=1

if [[ -z ${TEST:-} ]]; then
  sudo apt-get install -y supervisor
  if [[ -d /etc/supervisor/conf.d ]]; then
    sudo cp "$rendered_config_dir/supervisor-gemma.conf" /etc/supervisor/conf.d/supervisor-gemma.conf
  fi
  sudo supervisorctl reread
  sudo supervisorctl update
fi

if [[ -n ${TEST:-} ]]; then
  rm -rf "$backup_root"
else
  sudo rm -rf "$backup_root"
fi
activated=0
echo "Installed local Gemma service from $model_source to $install_root."
