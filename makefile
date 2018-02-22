
prepare:
	sudo apt-get update
	sudo apt-get install -y libssl-dev wget unzip python3-pip libsqlite3-dev python3-lxml
	sudo pip3 install sqlalchemy
	LC_ALL="en_US.UTF-8" sudo pip3 install -r requirements.txt

botscripts:
	cp scripts/*.sh $(HOME)
	mkdir -p user_data/dikantenyvaovao

cronconf: botscripts
	DB_PASSWD=$(DB_PASSWD) sudo bash -x deploy/configure-cron.sh

test:
	sudo apt-get install python3-nose python3-rednose
	python3.6 -m "nose" -vv --rednose test/

.PHONY: test

all: prepare botscripts cronconf

.PHONY: all