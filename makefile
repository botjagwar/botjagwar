PYTHON := python3.6
PIP := pip3.6
OPT_DIR := /opt/botjagwar
TEST_DIR := $(OPT_DIR)/test
CRON_DIR := /etc/cron.d

prepare:
	sudo apt-get update
	sudo apt-get install -y libssl-dev wget unzip python3-pip libsqlite3-dev libxml2-dev libxslt1-dev
	LC_ALL="en_US.UTF-8" sudo $(PIP) install -r requirements.txt
	sudo mkdir -p $(OPT_DIR)
	sudo chown $(USER) $(OPT_DIR)

define test_setup
	cp -r test $(OPT_DIR)
	cp -r test_data $(OPT_DIR)
	cp -r test_utils $(OPT_DIR)
endef

define test_teardown
	rm -rf $(OPT_DIR)/test
	rm -rf $(OPT_DIR)/test_data
	rm -rf $(OPT_DIR)/test_utils
endef

prepare_tests: install
	sudo apt-get install python3-nose python3-rednose
	sudo $(PIP) install nose

unit_tests: prepare_tests
	$(call test_setup)
	$(PYTHON) -m "nose" -v $(TEST_DIR)/unit_tests
	$(call test_teardown)

.PHONY: unit_tests

test: prepare_tests
	$(call test_setup)
	$(PYTHON) -m "nose" -v $(TEST_DIR)
	$(call test_teardown)

.PHONY: test

install:
	cp -r conf $(OPT_DIR)
	cp -r data $(OPT_DIR)
	cp -r database $(OPT_DIR)
	cp -r models $(OPT_DIR)
	cp -r modules $(OPT_DIR)
	cp -r user_data $(OPT_DIR)
	cp -r cron/* $(CRON_DIR)
	cp *.py $(OPT_DIR)
	cp scripts/*.sh $(OPT_DIR)
	mkdir -p $(OPT_DIR)/user_data/dikantenyvaovao

uninstall:
	sudo rm -rf $(OPT_DIR)

all: prepare install

.PHONY: all