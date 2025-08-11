Example files for deploying a production version of this software manually. The
`critterchat-nginx-conf` file should be customized to your installation and then
placed into `/etc/nginx/sites-available` and then symlinked into
`/etc/nginx/sites-enabled` to enable it. The `critterchat.service` file should
be customized to your installation and then placed into `/etc/systemd/system`.
Then, run `systemctl daemon-reload` to load the file, `systemctl enable critterchat`
to enable the service on boot and finally `systemctl start critterchat` to start
the service. If all goes to plan, systemd will manage the python backend and nginx
should provide SSL termination, attachment and static handling and proxy requests
to the python backend.
