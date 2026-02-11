#!/bin/sh
if python3 -m critterchat.manage --config config.yaml database create --existing-okay; then
	python3 -m critterchat.manage --config config.yaml database upgrade
	python3 -m critterchat --config config.yaml
else
	exit 1;
fi

