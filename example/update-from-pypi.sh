#! /bin/bash
#
# Example update script for bare metal installations tracking releases on PyPI.
# Automates the "Upgrading Production" steps from the README file with slight
# modifications to the source of the update. Note that you need to edit a few
# details about your own installation below.

set -e

SERVICE=critterchat
CONFIG=/path/to/config.yaml
VENV=/path/to/venv

# First, stop the running service.
sudo systemctl stop "${SERVICE}"

# Now, make sure the service is updated.
source "${VENV}/bin/activate"
python3 -m pip install --upgrade pip critterchat
python3 -m critterchat.manage --config "${CONFIG}" database upgrade
deactivate

# Now, restart the service.
sudo systemctl start "${SERVICE}"
echo "Done!"
