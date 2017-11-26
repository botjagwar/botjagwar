#!/bin/bash

export DB_PASSWD=$(cat $HOME/botjagwar/conf/BJDBModule/database_password | base64 -d)
echo ${DB_PASSWD}
sudo apt-get install -y mysql-server
sudo apt-get install -y python-mysqldb

mysql -u root --password=${DB_PASSWD} < data/schema.sql
mysql -u root --password=${DB_PASSWD} -D data_botjagwar < data/data_botjagwar.sql