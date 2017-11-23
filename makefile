setpass:
	mkdir -p conf/BJDBModule/
	python set_database_password.py -pass:${DB_PASSWD}

prepare:
	sudo apt-get update
	sudo apt-get install -y sudo
	sudo apt-get install -y libssl-dev
	sudo apt-get install -y wget
	sudo apt-get install -y unzip

python: prepare
	sudo apt-get install -y python2.7
	sudo apt-get install -y python-pip

install-python-deps: python
	LC_ALL="en_US.UTF-8" sudo pip install -r requirements.txt



botscripts:
	cp scripts/*.sh $(HOME)
	mkdir -p user_data/dikantenyvaovao

cronconf: botscripts
	DB_PASSWD=$(DB_PASSWD) sudo bash -x deploy/configure-cron.sh

monitoring:
	bash -x scripts/deploy-nginx.sh


database:
	bash -x deploy/setup-database.sh

dbconf: database
	bash -x deploy/configure-db.sh

test: database
	python test.py

clear:
	sudo apt-get remove -y mysql-server
	sudo apt-get purge -y mysql-server
	sudo apt-get autoremove -y nginx php-fpm php-mysql
	sudo apt-get autoremove -y python-pip python2.7 python-mysqldb

all: setpass install-python-deps database dbconf cronconf monitoring