# Running in Production

CritterChat uses nginx for SSL termination as well as a static resources server
for production instances. While it is possible to run an instance without nginx
it is not recommended. Offloading static assets takes load off of the server
itself so that it can concentrate on dynamic requests from clients. Additionally,
handling SSL termination is best left to a production-grade reverse proxy such as
nginx.

There are two options for running a production instance: bare metal and within a
docker container. With bare metal you manage the Python virtual environment,
dependencies, application service and database instance yourself. With a docker
container most of these are handled for you and you are solely responsible for
the container itself and the nginx reverse proxy siting in front of it. Both are
supported options for production hosting.

CritterChat prefers to use MySQL as the database for production instances. You
can choose to run with SQLite as your database instead. However, SQLite integration
is intended for fast local development. If you anticipate that your production
instance will remain fairly small then SQLite could be a reasonable option for you.
The included docker container only supports talking to a MySQL instance, so you
will need to either host on bare metal or modify the config and docker files in
`critterchat-docker/` to operate with SQLite instead.

# Bare Metal Hosting

In the `example/` directory you'll find a systemd service file for the backend
as well as an nginx configuration file for the nginx proxy portion. Both are meant
to be customized for your domain and certs as well as where you ultimately decide
to deploy CritterChat for a production instance. For SSL certificates, I recommend
using `certbot` which is a CLI interface to the Let's Encrypt project. If you want
to purchase certificates for use with SSL you can.

## Initial Setup

Initial setup is fairly straightforward. Pick a directory that you will deploy to,
create it, and make sure that it is owned by the user that will execute the server.
If you are using nginx as your reverse proxy and SSL termination then also make
sure that the directory is readable by the user that nginx uses since it will serve
static assets out of this directory as well. Copy `example/baremetal.mysql.config.yaml`
or `example/baremetal.sqlite.config.yaml` (depending on your database of choice) to
the directory you've just created and make sure that you customize it for your
installation. Create an attachments directory under the installation directory and
again make sure that it is owned by the server user and readable by the nginx
user.

Review your config.yaml to ensure that you've modified everything you need to.
Ensure that the `database` section points at your production database. Make sure
that the `cookie_key`, `password_key` and `attachment_key` are all set to a
random string of sufficient length. I recommend keeping them all different and using
a random generator that can give you a string of at least 48 characters. Note that
it is important to select good random values now and not change them in the future.
Changing these values in a production instance can have undesirable effects. If
you change the `cookie_key` in a production instance, all sessions will be logged
out. If you change `password_key` in production, all passwords will be invalidated
and you will have to manually change all of them. If you change `attachment_key`
in a production instance, all existing attachments will 404. So, choose good values
when setting up your instance and do not modify them. Make sure you rename your
instance to what you want to call it and edit the instance info text file to
include any rules or code of conduct. Finally, configure the attachment system.
Right now, only local storage is supported, so leave it set to local and leave
the prefix as-is. Update the directory to the absolute path of the attachment
directory you created above.

Now that your config is updated, create a Python virtual environment for the
production installation. I recommend sticking it in the deployed folder under a
directory called `venv` or similar. It doesn't matter where it is but you'll
want to keep organized. Once you've created that virtual environment you'll
be activating it every time you want to install updates. For now, activate it
and install the initial production instance by going into the `backend/`
directory and first running `python3 -m pip install --upgrade pip -r requirements.txt`
followed by `python3 -m pip install .`. This will install all dependencies,
the static resources and the code itself. If you have not built the frontend
for production, you will need to do this before running the above command by
going into the `frontend/` directory and running `npm run clean && npm run build`.

Now that the software is actually installed, you'll want to seed the database
which is presumably empty. In the same terminal that you have the activated
virtual environment that you just installed into, run the following command:

```
python3 -m critterchat.manage --config <path to your production config> database create
```

Now, you can test that the software is running by executing the following command
and seeing that it does not spit out any error messages or crashes:

```
python3 -m critterchat --config <path to your production config>
```

Now, make a copy of the `example/critterchat.service` file and place it into
`/etc/systemd/system`. Edit the user and group to match the user and group of the
production user you will run the backend service as. Edit the environment line
for the virtual environment to point at the absolute path of the virutual environment
you created and installed into. Edit the environment line for the config to point
at the absolute path of the production config you just edited. Edit the environment
line for the port to listen on to an available port above 2048 of your choosing.
Now, run `systemctl daemon-reload` to let systemd recognize the new service you
just created, and then `systemctl enable critterchat` to enable auto-starting on
reboot, and finally `systemctl start critterchat` to start the service. You can
use `journalctl -u critterchat` to see logs and verify that it started successfully.

Finally, we will set up the nginx proxy which will actually serve the production
traffic. Make a copy of the `example/critterchat-nginx.conf` file and place it
into `/etc/nginx/sites-available`. Edit the `server_name` line everywhere it appears
and change it to the domain or subdomain that you are running this under. Don't
forget to edit the `return` line in the top portion of the file to auto-promote
non-SSL traffic to SSL. Update the SSL certificate lines near the top and in the
location directives to point at your SSL certificates you obtained through `certbot`
or through purchasing certificates. Update all `proxy_pass` lines and ensure that
the port listed there is the same one that you chose in your systemd service configuration
above. Update the `alias` line under the `/attachments` location to point to the
same absolute path you configured for your attachments in your config.yaml. Update
the `alias` line under the `/static` location prefix to the same absolute path
you created for your venv. Take careful note to only edit the portion before the
`/lib` as the rest of that directory is where installing the backend will put
static resources.

Now, once this is done, symlink the file you just created into `/etc/nginx/sites-enabled`
to activate this and restart nginx using `systemctl restart nginx`. Once the restart
is complete you should have a production instance of CritterChat running on the
domain you've chosen!

## Running Without nginx

The above walkthrough as well as all of the baremetal examples assumes you're going
to use nginx as your reverse proxy and SSL termination. If you do not wish to set
this up and want to instead use the built-in SSL handler and asset serving code you
can but note that nginx will always be more performant than pure Python. You can
see the configuration options available to you by running the following command while
your production virtual environment is active:

```
python3 -m critterchat --config <path to your production config> --help
```

Specifically, you'll want to care about the `--port`, `--nginx-proxy`, `--cert` and
`--cert-key` options. It's recommended to still use the `example/critterchat.service`
file as a starting point but you'll need to make changes to the `ExecStart` line.
For the listen port, you'll need to set this to 443 because CritterChat will be handling
SSL directly from client requests. You'll need to get rid of the `--nginx-proxy`
option since you aren't using an nginx proxy. Failing to remove this could lead you to
being vulnerable to IP spoofing in logs. Next, you'll want to provide the SSL cert
files that you obtained from Let's Encrypt or purchasing a certificate. Pass the full
path to your certificate fullchain file to `--cert` and the full path to your certificate
private key file to `--cert-key`.

## Administration

Most of the administration for the server can be done in the CLI. At some point
I would like to be able to administer through the web interface as well but outside
of some basics this has not been implemented yet. The main administration interface
can be found by activating the production virtual environment and then running the
following command:

```
python3 -m critterchat.manage --help
```

This includes a bunch of stuff for adding and removing custom emojis, adding users,
activating and deactivating existing users, changing a user's password, generating
a password reset link for a user, creating an invite link to the instance, creating
public rooms, and managing the auto-join setting for public rooms. If you are using
one or more Mastodon instances as authentication providers it also provides commands
for registering against those instances and verifying things work. In the future
it will include a host of other helpful utilities. At the moment the software defaults
to allowing open signups but leaves users waiting to be activated. You can find users
to activate by running the following command:

```
python3 -m critterchat.manage --config <path to your production config> user list
```

You can then activate them using a similar command:

```
python3 -m critterchat.manage --config <path to your production config> user activate -u <username>
```

Right now there are virtually no moderator tools. If somebody gets too unruly or
spicy, you can deactivate their account using the following command. Note that if you
have set your account as an administrator you can deactivate their account by clicking
their profile and clicking the "deactivate user" button. Additionally, if you designate
a room as moderated and one or more moderators for a given public room they can mute
the user by clicking their profile and clicking the "mute user" button. Muting a user
will mark them as inactive in the room and stop them from messaging or reacting to messages.
Deactivating a user will log them out of all interfaces they're logged in on and prevent
them from logging back in again while also marking them inactive in all rooms they are in.

```
python3 -m critterchat.manage --config <path to your production config> user deactivate -u <username>
```

For more in-depth documentation of administration features please see [ADMINISTRATION.md](ADMINISTRATION.md).

## Upgrading Production

Once you've got everything installed, if you want to apply updates that you've
pulled from this repository, you can do so with the following steps. First,
actually pull the changes by refreshing your git repository. Go into the `frontend/`
directory and make sure you've built a new production bundle by running
`npm run clean && npm run build`. Then, activate the virtual environment you
created for the production instance. Now, stop the running server by executing
`systemctl stop critterchat`. Now, in the `backend/` directory, run
`python3 -m pip install --upgrade pip -r requirements.txt` followed by
`python3 -m pip install --upgrade .` to upgrade dependencies and install the new
version of CritterChat. Then run to following command to perform any schema migrations
that are present in the newly installed code:

```
python3 -m critterchat.manage --config <path to your production config> database upgrade
```

Finally, once all those steps are done, re-start the backend service with
`systemctl start critterchat`. If all went according to plan you should have the
new version running on your instance. Users that are currently logged in should get
a new update notification banner and you can refresh the page to load the new version.
Note that it is safe to run this while chatters are connected. While the upgrade is in
progress they will be blocked from sending new messages and will automatically reconnect
once the upgrade is successful. As a reminder, you can check the server logs for the
upgraded instance by running `journalctl -u critterchat`.

An example script that automates the entire upgrade process is available for you to
modify under `example/update-script`. Be sure to customize it to your installation.

# Docker Hosting

All of the files necessary for hosting a production instance with docker can be found in the
`critterchat-docker/` folder at the root of the repository. This includes a default config
file that will connect to the MySQL instance managed by docker as well as the `Dockerfile`
and `docker-compose.yml` files.

## Getting Started

To launch the default settings, simply clone the repo and navigate to `critterchat-docker/`,
then run:

```
docker compose up -d
```

to launch the app. This uses the config in the `critterchat-docker/` folder called
`docker.config.yaml` and provides bind mounts for the mysql database as well as the attachments
folder. After making any changes to the configuration, run:

```
docker compose restart
```

to reload the instance and load the new settings.

## Administration

Administration tools and other CLI interfaces can be accessed using:

```
docker exec -it CritterChat /bin/sh
```

which will drop you to a shell inside the container. Navigate to `/app/backend/` where you can
run the following command to talk to the management CLI:

```
python3 -m critterchat.manage --config config.yaml --help
```

## Upgrading

This has not been tested thoroughly, but should not cause any data loss since the database
and attachments are kept in a bind mount. In theory it should be as simple as:

```
docker compose down
git pull
docker image rm critterchat-docker-backend:latest
docker compose up -d
```

to pull the new code and relaunch it.
