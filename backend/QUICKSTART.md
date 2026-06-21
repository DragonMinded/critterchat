## Quick Start Guide

If you are on a modern debian-based operating system, you can run the following
commands in a terminal in order to get a basic version of CritterChat running in
as little time as possible:

```
# Install necessary system dependencies for CritterChat
sudo apt install python3 python3-dev python3-pip pkg-config \
         libmysqlclient-dev build-essential ffmpeg pipx

# Install CritterChat into your user path using PipX
pipx install critterchat

# Initialize local configuration
critterchat-manage example write --directory .
critterchat-manage --config baremetal.sqlite.config.yaml database create

# Add a test user that you can use to log in with
critterchat-manage --config baremetal.sqlite.config.yaml user create -u test -p test

# Add a test room that you will join when you log in
critterchat-manage --config baremetal.sqlite.config.yaml room create -n "Test Room" -a on

# Run the frontend, which can be viewed at http://localhost:5678
critterchat --config baremetal.sqlite.config.yaml
```

Once you've run those steps, you can go to [http://localhost:5678/](http://localhost:5678)
and login with username "test" and password "test" to start poking around.
