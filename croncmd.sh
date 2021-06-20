#!/bin/bash


X=$(ps aux | grep dsmt | wc -l)


if [ $X -le 1 ] 
then
	echo "dsmt is not running, starting it now..."
	dsmt
else
	echo "dsmt is already running"
fi
