#!/usr/bin/env bash

cd $HOME/botjagwar


ARCHIVEREPOSITORY=$(cat conf/BJDBModule/archive_repo)
SQLREP=$ARCHIVEREPOSITORY/sql
UNKNOWNWORDSREP=$ARCHIVEREPOSITORY/unknowns

if [ ! -d "$SQLREP" ]; then
  mkdir -p $SQLREP
  if [ ! -d "$UNKNOWNWORDSREP" ]; then
    mkdir -p $UNKNOWNWORDSREP
  fi
fi

gzip $HOME/botjagwar/word_database.db > $SQLREP/$(date -u +%Y-%m-%d).db.gz
cat user_data/dikantenyvaovao/word_hits | gzip -f > $UNKNOWNWORDSREP/$(date -u +%Y-%m-%d).txt.gz