#!/bin/bash

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"



LOGFILE="$DIR/log.txt"
nohup python "$DIR/dsmt/dsmt_app.py" > $LOGFILE &

