#!/bin/bash

echo "Prepare python environment"

set -x

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


if [[ -z $virtualenv_exe ]]; then
  echo "No virtual env commands found. Install one of them manually."
  exit 1
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
  $virtualenv_exe $opt_dir/pyenv
  $virtualenv_exe $opt_dir/pyenv
  source $opt_dir/pyenv/bin/activate
fi

cd "$src_dir"
python3 -m pip install -r requirements.txt

sudo mkdir -p $opt_dir/user_data

sudo cp -r $src_dir/api $opt_dir
sudo cp -r $src_dir/conf $opt_dir
sudo cp -r $src_dir/data $opt_dir
sudo cp -r $src_dir/scripts $opt_dir
sudo cp -r $src_dir/*.py $opt_dir

if [[ -z $TEST ]]; then
  # Install dependencies if NOT in test mode
  # this should allow for an increase of the speed-up regarding build time and is not needed
  # anyway by the unit tests when in testing mode
  sudo apt-get install -y haproxy
  sudo apt-get install -y redis-server
  sudo cp conf/haproxy.cfg $opt_dir/conf/
  sudo apt-get install -y supervisor

  if [[ -d /etc/supervisor/conf.d ]]; then
    sudo cp $src_dir/conf/supervisor-botjagwar.conf /etc/supervisor/conf.d/supervisor-botjagwar.conf

    # replace current from a potentially privileged user down to a non-privileged one. Pywikibot user
    # might be configured for the user and but not for the root user, as generally advised.
    sudo sed -i "s/user=user/user=`whoami`/g" /etc/supervisor/conf.d/supervisor-botjagwar.conf
    sudo sed -i "s/\/home\/user/\/home\/`whoami`/g" /etc/supervisor/conf.d/supervisor-botjagwar.conf
  fi
  if [[ -z $RESTART_ALL ]]; then
    echo "Supervisor installation is complete. Reloading config"
    sudo supervisorctl reload
  fi
fi

if [[ ! -z $INSTALL_PG ]]; then
  # Feature coming soon
  echo "Automatic postgreSQL installation/configuration is currently not supported."
fi

if [[ ! -d ${opt_dir}/bin ]]; then
  mkdir -p ${opt_dir}/bin
fi

cp bin/postgrest $opt_dir/bin


sudo chown "`whoami`":"`whoami`" -R $opt_dir

