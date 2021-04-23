#/bin/bash

LD_LIBRARY_PATH=/home/server/.local/lib/python3.8/site-packages/PyQt5/Qt/lib:$LD_LIBRARY_PATH
export LD_LIBRARY_PATH

PYTHONPATH=/home/server/.local/lib/python3.8/site-packages
export PYTHONPATH

python3 ./main.py -M -Lh
