#!/bin/sh

OPTS=""

if [ -n "$BEHIND_NGINX_PROXY" ]; then
	OPTS="$OPTS --nginx-proxy 1"
fi

if python3 -m critterchat.manage --config config.yaml database create --existing-okay; then
	python3 -m critterchat.manage --config config.yaml database upgrade
	echo "Running Command: python3 -m critterchat --config config.yaml $OPTS"
	python3 -m critterchat --config config.yaml $OPTS
else
	exit 1;
fi

