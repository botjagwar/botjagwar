#!/usr/bin/env bash

cd $HOME/botjagwar

DBPASS=$(cat conf/BJDBModule/database_password | base64 -d)
ARCHIVEREPOSITORY=$(cat conf/BJDBModule/archive_repo)

if [ ! -d "$ARCHIVEREPOSITORY" ]; then
  mkdir -p $ARCHIVEREPOSITORY
fi

mysqldump --all-databases --password=$DBPASS --user=root | gzip -f > $ARCHIVEREPOSITORY/$(date -u +%Y-%m-%d).gz
