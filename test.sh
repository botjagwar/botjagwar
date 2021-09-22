#!/bin/bash
echo "Prepare python environment"
opt_dir=/opt/botjagwar
src_dir=$(pwd)

# Setup test environment
set -x
bash -xe install.sh

if [[ -f $opt_dir/conf/config.ini ]]; then
  sudo mv $opt_dir/conf/config.ini $opt_dir/conf/config.normal.ini
  sudo mv $opt_dir/conf/test_config.ini $opt_dir/conf/config.ini
fi

source $opt_dir/pyenv/bin/activate
python -m pip install nose
if [[ $NORUN == 1 ]]; then
  exit
fi

cd "$src_dir" || exit
python -m nose test
nosetests3 --with-coverage --cover-html --cover-html-dir=/tmp -vv test

if [[ -f $opt_dir/conf/config.ini ]]; then
  sudo rm $opt_dir/conf/config.ini
  sudo mv $opt_dir/conf/config.normal.ini $opt_dir/conf/config.ini
fi
