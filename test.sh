#!/bin/bash
echo "Prepare python environment"
opt_dir=/opt/botjagwar
src_dir=$(pwd)

export TEST=1

# Setup test environment
set -x
bash -xe install.sh
set -e
if [[ -f $opt_dir/conf/config.ini ]]; then
  sudo mv $opt_dir/conf/config.ini $opt_dir/conf/config.normal.ini
  sudo mv $opt_dir/conf/test_config.ini $opt_dir/conf/config.ini
fi

source $opt_dir/pyenv/bin/activate

python -m pip install pytest==7.2.1
python -m pip install pytest-cov==4
python -m pip install parameterized

if [[ $NORUN == 1 ]]; then
  exit
fi

cd "$src_dir" || exit

pytest -vv --cov-report=html --cov=api test/unit_tests
if [[ -f $opt_dir/conf/config.ini ]]; then
  sudo rm $opt_dir/conf/config.ini
  sudo mv $opt_dir/conf/config.normal.ini $opt_dir/conf/config.ini
fi
