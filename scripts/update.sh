#!/bin/bash
set -e

cd /tmp

# Cleanup previous updates
sudo rm -rf /tmp/botjagwar

# Save data if exists
if [ -d "/opt/botjagwar" ]; then
    if [ -f /tmp/botjagwar_saved_data ]; then
        echo "Deleting old save"
        sudo rm -rf /tmp/botjagwar_saved_data
    fi
    sudo mkdir -p /tmp/botjagwar_saved_data
    sudo cp -r /opt/botjagwar/data /tmp/botjagwar_saved_data
    sudo cp -r /opt/botjagwar/user_data /tmp/botjagwar_saved_data

    echo "Stopping all python programs"
    if ps aux | grep python3.6; then
        if sudo killall -9 python3.6; then
            echo 'Python scripts killed.'
        else
            echo 'No Python scripts killed.'
        fi
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

# Update is finished, copy old files
sudo cp -r /tmp/botjagwar_saved_data/data /opt/botjagwar
sudo cp -r /tmp/botjagwar_saved_data/user_data /opt/botjagwar
echo "update ok"
sudo service cron start
