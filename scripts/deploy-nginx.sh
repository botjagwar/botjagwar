#!/bin/bash

echo "manavao bazy";
apt-get update;
sleep 1;

echo "mametraka NGINX";
apt-get install nginx -y; 
sleep 1;

echo "mandika ny rakitr'i NGINX any @ tokony hisy azy";
cp -r cd $HOME/botjagwar/deploy/nginx /etc/nginx;
service nginx restart;
sleep 1;



