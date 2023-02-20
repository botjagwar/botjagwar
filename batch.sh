#!/bin/bash
source /opt/botjagwar/pyenv/bin/activate

FR_CATEGORY="user_data/list_fr_Verbes en bulgare"
for page in $(cat "$FR_CATEGORY"); do
  echo ">>>> $page ($page) <<<<<"
  curl -X POST http://localhost:8000/wiktionary_page/fr -H 'Content-Type: application/json' -d "{\"title\":\"$page\"}"
done
