#!/bin/bash
echo "Prepare python environment"
src_dir=$(pwd)
test_install_root=$(mktemp -d /tmp/botjagwar-test-install.XXXXXX)
opt_dir="$test_install_root/botjagwar"

cleanup() {
  sudo rm -rf "$test_install_root"
}
trap cleanup EXIT

export TEST=1
export PYWIKIBOT_NO_NETWORK=1
export BOTJAGWAR_CONF_PATH="$src_dir/conf"
export BOTJAGWAR_INSTALL_DIR="$opt_dir"

# Setup test environment
set -ex
bash install.sh
first_release=$(readlink -f "$opt_dir/current")
printf '\n# reinstall-persistence-sentinel\n' >> "$opt_dir/shared/etc/config.ini"
touch "$opt_dir/shared/var/user_data/reinstall-persistence-sentinel"

BOTJAGWAR_RELEASE_ID="test-reinstall-$$" bash install.sh
second_release=$(readlink -f "$opt_dir/current")
test "$first_release" != "$second_release"
test -d "$first_release"
test -f "$opt_dir/shared/var/user_data/reinstall-persistence-sentinel"
grep -q reinstall-persistence-sentinel "$opt_dir/shared/etc/config.ini"

if BOTJAGWAR_RELEASE_ID="failed-candidate-$$" POSTGREST_INSTANCES=99 bash install.sh; then
  echo "An invalid candidate unexpectedly activated." >&2
  exit 1
fi
test "$(readlink -f "$opt_dir/current")" = "$second_release"
test ! -e "$opt_dir/releases/failed-candidate-$$"

if BOTJAGWAR_RELEASE_ID="test-reinstall-$$" bash install.sh; then
  echo "A duplicate release identifier unexpectedly succeeded." >&2
  exit 1
fi
test "$(readlink -f "$opt_dir/current")" = "$second_release"
test -d "$second_release"

test -L "$opt_dir/current"
test -x "$opt_dir/current/bin/postgrest"
test -x "$opt_dir/current/bin/configure-atlas-supervisor"
test -L "$opt_dir/current/conf/config.ini"
test -L "$opt_dir/current/user_data"
cmp "$src_dir/user_data/basic_english.txt" "$opt_dir/current/user_data/basic_english.txt"

source "$opt_dir/current/pyenv/bin/activate"

export UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/botjagwar-uv-cache}"
if ! command -v uv >/dev/null 2>&1; then
  python -m pip install uv
fi
uv pip install pytest==7.4.4 pytest-cov==4 pytest-mock parameterized

if [[ $NORUN == 1 ]]; then
  exit
fi

cd "$src_dir" || exit

pytest -vv --cov-report=html \
  --cov=api.translation_v2 --cov=api.services --cov=api.parsers --cov=api.entryprocessor --cov=api.serialisers --cov=api.importer \
  --cov=entry_translator_v2 --cov=api.storage \
  --cov=scripts --cov=supervisor_control_service --cov=configure_atlas_supervisor \
  --cov-fail-under=85 \
  test/unit_tests

if [[ ${SKIP_FRONTEND:-0} == 1 ]]; then
  echo "Skipping frontend checks by request."
elif command -v npm >/dev/null 2>&1; then
  npm ci --prefix frontend
  npm run lint --prefix frontend
  npm test --prefix frontend
  npm run build --prefix frontend
else
  echo "Node.js is not installed; skipping frontend checks."
fi
