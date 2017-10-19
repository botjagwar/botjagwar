setpass:
	mkdir -p conf/BJDBModule/
	python set_database_password.py -pass:$(DB_PASSWD)

prepare:
	apt-get update
	apt-get install -y sudo
	sudo apt-get install -y libssl-dev
	sudo apt-get install -y wget
	sudo apt-get install -y unzip

python: prepare
	sudo apt-get install -y python2.7
	sudo apt-get install -y python-pip

install-python-deps: python
	LC_ALL="en_US.UTF-8" sudo pip install -r requirements.txt



botscripts:
	cp scripts/dikantenyvaovao-start.sh $(HOME)
	cp scripts/fitenytsyfantatra.sh $(HOME)
	cp scripts/list-wikis.sh $(HOME)
	cp scripts/vaovaowikimedia.sh $(HOME)

cronconf: botscripts
	DB_PASSWD=$(DB_PASSWD) sudo bash -x deploy/configure-cron.sh

monitoring:
	bash -x scripts/deploy-nginx.sh


database:
	DB_PASSWD=$(DB_PASSWD) sudo bash -x deploy/setup-database.sh

dbconf: database
	DB_PASSWD=$(DB_PASSWD) sudo bash -x deploy/configure-db.sh

schema: database
	sudo service mysql start
	mysql -u root --password=$(DB_PASSWD) < data/schema.sql

data: schema database
	sudo service mysql start
	mysql -u root --password=$(DB_PASSWD) -D data_botjagwar < data/data_botjagwar.sql
	sudo bash -x scripts/deploy.sh

test: database
	python test.py



clear:
	sudo apt-get remove -y mysql-server
	sudo apt-get purge -y mysql*
	sudo apt-get autoremove -y nginx php-fpm php-mysql
	sudo apt-get autoremove -y python-pip python2.7 python-mysqldb


all: install-python-deps data dbconf cronconf monitoring
