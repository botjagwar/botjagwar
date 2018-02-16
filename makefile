
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
	LC_ALL="en_US.UTF-8" sudo pip3 install -r requirements.txt

install-python-deps: python
	sudo apt-get install -y python3-lxml

botscripts:
	cp scripts/*.sh $(HOME)
	mkdir -p user_data/dikantenyvaovao

cronconf: botscripts
	DB_PASSWD=$(DB_PASSWD) sudo bash -x deploy/configure-cron.sh

test:
	sudo apt-get install python3-nose python3-rednose
	python3.6 -m "nose" -vv --rednose test/

.PHONY: test


all: install-python-deps python-requirements cronconf