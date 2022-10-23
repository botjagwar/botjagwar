#!/bin/bash
source /opt/botjagwar/pyenv/bin/activate
python api/page_lister.py mg "Endriky ny matoanteny amin'ny teny soedoa"

FR_CATEGORY="user_data/list_mg_Endriky ny matoanteny amin'ny teny soedoa"
for page in $(cat "$FR_CATEGORY"); do
  echo ">>>> $page ($page) <<<<<"
  curl -X POST http://localhost:8000/wiktionary_page/fr -H 'Content-Type: application/json' -d "{\"title\":\"$page\"}"
done
