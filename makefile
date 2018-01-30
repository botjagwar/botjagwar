setpass:
	mkdir -p conf/BJDBModule
	python set_database_password.py -pass:${DB_PASSWD}

prepare:
	sudo apt-get update
	sudo apt-get install -y sudo
	sudo apt-get install -y libssl-dev
	sudo apt-get install -y wget
	sudo apt-get install -y unzip

python: prepare
	sudo apt-get install -y python3.6-dev
	sudo apt-get install -y python3-pip
	sudo pip3 install sqlalchemy

python-requirements: python
	LC_ALL="en_US.UTF-8" sudo pip install -r requirements.txt

install-python-deps: python
	sudo apt-get install -y python3-lxml


botscripts:
	cp scripts/*.sh $(HOME)
	mkdir -p user_data/dikantenyvaovao

cronconf: botscripts
	DB_PASSWD=$(DB_PASSWD) sudo bash -x deploy/configure-cron.sh

test:
	sudo apt-get install python3-nose
	nosetests3 --py3where=/usr/bin -s -v .

.PHONY: test


all: setpass install-python-deps python-requirements cronconf