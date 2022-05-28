#!/bin/bash
echo "Prepare python environment"
opt_dir=/opt/botjagwar
src_dir=$(pwd)

# Setup test environment
set -x
bash -xe install.sh
set -e
if [[ -f $opt_dir/conf/config.ini ]]; then
  sudo mv $opt_dir/conf/config.ini $opt_dir/conf/config.normal.ini
  sudo mv $opt_dir/conf/test_config.ini $opt_dir/conf/config.ini
fi

source $opt_dir/pyenv/bin/activate

python -m pip install nose
python -m pip install parameterized

if [[ $NORUN == 1 ]]; then
  exit
fi

cd "$src_dir" || exit

python -m nose -vv test --with-coverage --cover-html --cover-min-percentage=66 --cover-package=api,database,model
if [[ -f $opt_dir/conf/config.ini ]]; then
  sudo rm $opt_dir/conf/config.ini
  sudo mv $opt_dir/conf/config.normal.ini $opt_dir/conf/config.ini
fi
