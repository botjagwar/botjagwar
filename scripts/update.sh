#!/bin/bash
set -e

cd /tmp

# Cleanup previous updates
sudo rm -rf /tmp/botjagwar

# Save data if exists
if [ -d "/opt/botjagwar" ]; then
    sudo rm -rf /tmp/botjagwar_saved_data
    sudo mkdir -p /tmp/botjagwar_saved_data
    sudo cp -r /opt/botjagwar/data /tmp/botjagwar_saved_data
    sudo cp -r /opt/botjagwar/user_data /tmp/botjagwar_saved_data

    echo "Stopping all python programs"
    if ps aux | grep python3.6; then
        sudo killall -9 python3.6
    fi
fi

# Stopping cron and removing old install
sudo service cron stop;

# Fetching code and deploying it on target
git clone https://github.com/radomd92/botjagwar.git
cd botjagwar
make uninstall
make prepare
make install

# Testing the install
sudo cp -r test /opt/botjagwar/test
sudo python3.6 -m pip install nose
PYWIKIBOT2_NO_USER_CONFIG=1 sudo python3.6 -m nose -v /opt/botjagwar/test
sudo rm -rf /opt/botjagwar/test

# Update is finished, copy old files
sudo cp -r /tmp/botjagwar_saved_data/data /opt/botjagwar/data
sudo cp -r /tmp/botjagwar_saved_data/user_data /opt/botjagwar/user_data
echo "update ok"
sudo service cron start