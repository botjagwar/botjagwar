#!/usr/bin/env bash

cd $HOME/botjagwar

DBPASS=$(cat conf/BJDBModule/database_password | base64 -d)
ARCHIVEREPOSITORY=$(cat conf/BJDBModule/archive_repo)
SQLREP=$ARCHIVEREPOSITORY/sql
UNKNOWNWORDSREP=$ARCHIVEREPOSITORY/unknowns

if [ ! -d "$SQLREP" ]; then
  mkdir -p $SQLREP
  if [ ! -d "$UNKNOWNWORDSREP" ]; then
    mkdir -p $UNKNOWNWORDSREP
  fi
fi

mysqldump --all-databases --password=$DBPASS --user=root | gzip -f > $SQLREP/$(date -u +%Y-%m-%d).sql.gz
cat user_data/dikantenyvaovao/word_hits | gzip -f > $UNKNOWNWORDSREP/$(date -u +%Y-%m-%d).txt.gz