#!/bin/bash

src_dir=`pwd`
opt_dir_ctranslate=/opt/ctranslate

echo "Installing ctranslate for NLLB"
if [[ -d $opt_dir_ctranslate ]]; then
  sudo rm -rf $opt_dir_ctranslate
fi
sudo mkdir -p $opt_dir_ctranslate
sudo chown "`whoami`":"`whoami`" -R $opt_dir_ctranslate
cp -r $src_dir/ctranslate.py $opt_dir_ctranslate

cd $opt_dir_ctranslate

virtualenv -p python3 venv
source venv/bin/activate
python3 -m pip install -r $src_dir/requirements-ctranslate.txt

if [[ -d ~/nllb-200-3.3B ]]; then
  cp -r ~/nllb-200-3.3B $opt_dir_ctranslate
  mv $opt_dir_ctranslate/nllb-200-3.3B/sentencepiece.bpe.model $opt_dir_ctranslate
else
  echo "Please download the NLLB 3.3B model from huggingface and place it in ~/nllb-200-3.3B"
  echo "and then rerun this script."
  exit 1
fi
