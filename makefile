PYTHON := python3
PIP := $(PYTHON) -m pip
OPT_DIR := /opt/botjagwar
TEST_DIR := $(OPT_DIR)/test
CRON_DIR := /etc/cron.d

define create_dirs
	sudo mkdir -p $(OPT_DIR)
	if ! sudo chown $(USER) $(OPT_DIR); then echo "chown failed (user is not defined)"; fi
	sudo mkdir -p $(CRON_DIR)
	mkdir -p $(OPT_DIR)/user_data/dikantenyvaovao
endef

define delete_dirs
	sudo rm -rf $(OPT_DIR)/user_data/dikantenyvaovao
	sudo rm -rf $(OPT_DIR)
	sudo rm -rf $(CRON_DIR)/botjagwar*
endef

prepare:
	sudo apt-get update
	sudo apt-get install -y \
	    libssl-dev \
	    wget unzip \
	    python3-pip \
	    python3-pip \
	    libsqlite3-dev \
	    redis-server \
	    libxml2-dev \
	    libxslt1-dev
	LC_ALL="en_US.UTF-8" sudo $(PIP) install -r requirements.txt

define test_setup
	cp -r test $(OPT_DIR)
	cp -r test_data $(OPT_DIR)
	cp -r test_utils $(OPT_DIR)
	cp $(OPT_DIR)/conf/config.ini $(OPT_DIR)/conf/config_new.ini
	cp $(OPT_DIR)/conf/test_config.ini $(OPT_DIR)/conf/config.ini
endef

define test_teardown
	rm -rf $(OPT_DIR)/test
	rm -rf $(OPT_DIR)/test_data
	rm -rf $(OPT_DIR)/test_utils
	cp $(OPT_DIR)/conf/config_new.ini $(OPT_DIR)/conf/config.ini
endef

define copy_crontab
	sudo cp -r cron/botjagwar $(CRON_DIR)
	sudo sed -i "s/cronuser/$(USER)/" $(CRON_DIR)/botjagwar
endef

prepare_tests: install
	sudo apt-get install python3-nose python3-rednose
	sudo $(PIP) install nose


unit_tests: prepare_tests
	$(call test_setup)
	$(PYTHON) -m "nose" -v $(TEST_DIR)/unit_tests
	$(call test_teardown)

.PHONY: unit_tests

additional_tests: prepare_tests
	$(call test_setup)
	$(PYTHON) -m "nose" -v additional_tests

.PHONY: additional_tests

test: prepare_tests
	$(call test_setup)
	PYWIKIBOT2_NO_USER_CONFIG=1 $(PYTHON) -m "nose" -v $(TEST_DIR)
	$(call test_teardown)

.PHONY: test

complexity:
	sudo pip3.6 install xenon
	xenon --max-absolute B --max-modules C --max-average B .

.PHONY: complexity

install:
	$(call create_dirs)
	git describe --tags > data/version
	cp -r api $(OPT_DIR)
	cp -r conf $(OPT_DIR)
	cp -rn data $(OPT_DIR)
	cp -r database $(OPT_DIR)
	cp -r object_model $(OPT_DIR)
	cp -rn user_data $(OPT_DIR)
	$(call copy_crontab)
	cp *.py $(OPT_DIR)
	cp scripts/*.sh $(OPT_DIR)

uninstall:
	$(call delete_dirs)

all: prepare install

.PHONY: all
