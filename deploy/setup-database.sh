#!/bin/bash

echo $(DB_PASSWD)
echo "mysql-server mysql-server/root_password password $(DB_PASSWD)" | sudo debconf-set-selections
echo "mysql-server mysql-server/root_password_again password $(DB_PASSWD)" | sudo debconf-set-selections
sudo -E apt-get -q -y install mysql-server
sudo apt-get install -y python-mysqldb