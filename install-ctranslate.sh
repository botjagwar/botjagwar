#!/bin/bash

src_dir=`pwd`
opt_dir_ctranslate=/opt/ctranslate

echo "Installing ctranslate for NLLB"
if [[ -d $opt_dir_ctranslate ]]; then
  sudo rm -rf $opt_dir_ctranslate
fi
sudo mkdir -p $opt_dir_ctranslate
sudo chown "`whoami`":"`whoami`" -R $opt_dir_ctranslate
cp -r $src_dir/ctranslate.py $opt_dir_ctranslate

cd $opt_dir_ctranslate

if [[ -z `which python3` ]]; then
  echo "Python3 is not installed. Please install it manually."
  exit 1
fi


# Check for virtualenv and venv
# Check for Python installation
if ! command -v python3 >/dev/null 2>&1; then
  echo "Python3 is not installed."
  exit 1
fi

# Check if virtualenv command exists
if command -v virtualenv >/dev/null 2>&1; then
  echo "'virtualenv' command is available."
  virtualenv_exe="virtualenv"
fi

# Check if venv (built-in) is available
if python3 -m venv --help >/dev/null 2>&1; then
  echo "Python 'venv' module is available."
  virtualenv_exe="python3 -m venv"
fi


set -e

$virtualenv_exe -p python3 venv
source venv/bin/activate
python3 -m pip install -r $src_dir/requirements-ctranslate.txt

if [[ -z $TEST ]]; then
  # Install dependencies if NOT in test mode
  # this should allow for an increase of the speed-up regarding build time and is not needed
  # anyway by the unit tests when in testing mode
  sudo apt-get install -y haproxy
  sudo apt-get install -y redis-server
  sudo cp conf/haproxy.cfg $opt_dir_ctranslate/conf/
  sudo apt-get install -y supervisor

  if [[ -d /etc/supervisor/conf.d ]]; then
    sudo cp $src_dir/conf/supervisor-ctranslate.conf /etc/supervisor/conf.d/supervisor-ctranslate.conf
    sudo sed -i "s/user=user/user=`whoami`/g" /etc/supervisor/conf.d/supervisor-ctranslate.conf
    sudo sed -i "s/\/home\/user/\/home\/`whoami`/g" /etc/supervisor/conf.d/supervisor-ctranslate.conf
  fi
  if [[ -z $RESTART_ALL ]]; then
    echo "Supervisor installation is complete. Reloading config"
    sudo supervisorctl reload
  fi
fi


if [[ -d ~/nllb-200-3.3B ]]; then
  cp -r ~/nllb-200-3.3B $opt_dir_ctranslate
  mv $opt_dir_ctranslate/nllb-200-3.3B/sentencepiece.bpe.model $opt_dir_ctranslate
else
  echo "Please download the NLLB 3.3B model from huggingface and place it in ~/nllb-200-3.3B"
  echo "and then rerun this script."
  exit 1
fi
