#!/bin/bash
echo "Prepare python environment"
set -xe
if [[ `which virtualenv` == 1 ]]; then
  sudo python3 -m pip install virtualenv
fi

src_dir=`pwd`
opt_dir=/opt/botjagwar
current_user=`whoami`

# Create virtual environment
if [[ -d $opt_dir ]]; then
  sudo rm -rf $opt_dir
fi

sudo mkdir -p $opt_dir
sudo chown $current_user $opt_dir
if [[ ! -d $opt_dir/pyenv ]]; then
  set -e
  python3 -m virtualenv $opt_dir/pyenv
  source $opt_dir/pyenv/bin/activate
fi


cd $src_dir
python3 -m pip install -r requirements.txt

sudo mkdir -p $opt_dir/user_data

sudo cp -r $src_dir/api $opt_dir
sudo cp -r $src_dir/conf $opt_dir
sudo cp -r $src_dir/data $opt_dir
sudo cp -r $src_dir/database $opt_dir
sudo cp -r $src_dir/object_model $opt_dir
sudo cp -r $src_dir/scripts $opt_dir
sudo cp -r $src_dir/*.py $opt_dir
