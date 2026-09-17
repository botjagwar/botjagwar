#!/bin/bash
source /opt/botjagwar/pyenv/bin/activate
#python api/page_lister.py fr "Verbes en bulgare"

CATEGORY="$1"
for page in $(cat "$CATEGORY"); do
  echo ">>>> $page ($page) <<<<<"
  curl --fail-with-body --retry 10 --retry-all-errors --retry-delay 3 \
    -X POST http://localhost:8000/wiktionary-pages/en/jobs \
    -H 'Content-Type: application/json' \
    -d "{\"title\":\"$page\"}"
done
