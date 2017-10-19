setpass:
	mkdir -p conf/BJDBModule/
	python set_database_password.py -pass:$(DB_PASSWD)

prepare: setpass
	sudo apt-get update
	sudo apt-get install -y sudo
	sudo apt-get install -y libssl-dev
	sudo apt-get install -y wget
	sudo apt-get install -y unzip

python: prepare
	sudo apt-get install -y python2.7
	sudo apt-get install -y python-pip

install-deps: python
	LC_ALL="en_US.UTF-8" sudo pip install -r requirements.txt

database:
	DB_PASSWD=$(DB_PASSWD) sudo bash -x deploy/setup-database.sh

dbconf:
	DB_PASSWD=$(DB_PASSWD) sudo bash -x deploy/configure-db.sh

cronconf:
	DB_PASSWD=$(DB_PASSWD) sudo bash -x deploy/configure-cron.sh

botscripts:
	cp scripts/dikantenyvaovao-start.sh $(HOME)
	cp scripts/fitenytsyfantatra.sh $(HOME)
	cp scripts/list-wikis.sh $(HOME)
	cp scripts/vaovaowikimedia.sh $(HOME)

monitoring:
	bash -x scripts/deploy-nginx.sh

schema: database
	sudo service mysql start
	mysql -u root --password=$(DB_PASSWD) < data/schema.sql

test: database
	python test.py

data: schema database
	sudo service mysql start
	mysql -u root --password=$(DB_PASSWD) -D data_botjagwar < data/data_botjagwar.sql
	sudo bash -x scripts/deploy.sh

clear:
	sudo apt-get remove -y mysql-server
	sudo apt-get purge -y mysql*
	sudo apt-get autoremove -y nginx php-fpm php-mysql
	sudo apt-get autoremove -y python-pip python2.7 python-mysqldb

all: python install-deps data botscripts
