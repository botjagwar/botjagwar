DB_PASSWD := $(shell bash -c 'read -s -p "Atsofohy ny (ho) tenimiafin'ny banky angonao / Please enter your (future) database password: " pwd; echo $$pwd')

setpass:
	mkdir -p conf/BJDBModule/
	python set_database_password.py -pass:$(DB_PASSWD)

prepare: setpass
	sudo apt-get update
	apt-get install -y wget
	apt-get install -y unzip

python: prepare
	sudo apt-get install -y python2.7
	sudo apt-get install -y python-pip

install-deps: python
	LC_ALL="en_US.UTF-8" pip install -r requirements.txt

database: install-deps
	echo $(DB_PASSWD)
	echo "mysql-server mysql-server/root_password password $(DB_PASSWD)" | sudo debconf-set-selections
	echo "mysql-server mysql-server/root_password_again password $(DB_PASSWD)" | sudo debconf-set-selections
	sudo -E apt-get -q -y install mysql-server
	sudo apt-get install -y python-mysqldb

schema: database
	mysql -u root --password=$(DB_PASSWD) < data/schema.sql

test: database
	python test.py

data: schema database
	mysql -u root --password=$(DB_PASSWD) -D data_botjagwar < data/data_botjagwar.sql

lemp-stack: database
	sudo apt-get install -y nginx
	sudo apt-get install -y php-fpm php-mysql

clear:
	sudo apt-get remove -y mysql-server
	sudo apt-get purge -y mysql*
	sudo apt-get autoremove -y nginx php-fpm php-mysql
	sudo apt-get autoremove -y python-pip python2.7 python-mysqldb

all: python install-deps data lemp-stack
