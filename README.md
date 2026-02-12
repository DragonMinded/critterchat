# CritterChat

A web-based chat program that you can host yourself, providing direct messaging
and chat within public rooms. Started as a middle finger to Discord and now evolving
slowly into its own thing. CritterChat focuses on ease of experience over highly
technical things like end-to-end encryption. As of right now, instances are
standalone, but I would like to implement some sort of federation between instances
that can be enabled or disabled per-instance.

## Feature List

 - Web frontend with basic mobile and desktop support.
 - Public rooms with optional auto-join for new members.
 - Direct messages between users on the instance.
 - Direct messages and public rooms have an editable name and topic.
 - User profile support with ability to view other chatters' profiles.
 - Custom emoji support controlled by the instance administrator.
 - Preferences for most appearance settings and optional notification sounds.
 - Image attachment support so images can be sent with messages.
 - Various sign-up modes such as open registration, admin-approval and invite codes.
 - Integration with Mastodon's OAuth for account creation and auth.
 - Collects absolutely no personal information, contains no tracking code.

## Wishlist

 - Message editing.
 - Message deleting.
 - Message reactions.
 - Reply to message.
 - Now typing indicators.
 - Read receipts.
 - Pinned messages.
 - Sticker support.
 - Moderation tools for network admin (global mute, global ban, etc).
 - Moderation tools for individuals (block user, allow messages, allow in search, etc.).
 - Emoji auto-categorization by prefix.
 - Arbitrary file attachments.
 - Sitewide CSS themeing with CSS moved to themes directory.
 - Per-chat CSS themeing for direct messages and rooms.
 - Ability to set a personal nickname for a user that only you can see.
 - Port Myno's Pictochat over from PyStreaming, allow drawing and remixing.
 - Link auto-sanitization to remove tracking info.
 - Multi-account support.
 - Inter-instance direct message and room support.

## Needed Help

If you're looking for something to contribute and something on this or the above
list sparks your interest we would be very grateful for a contribution! Please
get in touch so we can work out the direction you plan to take.

 - Containerization and simplifying deployment/updates.
 - UX design work and help with themes.
 - Accessibility help, audits and fixes.
 - Testing and support for non-standard browsers such as Safari.
 - SVGs for graphics for default avatar/room pictures, iconography on the frontend.
 - Documentation clarification or correction, both in code and related markdown files.
 - Support for more attachment backends.
 - Support for more authentication provider flows.
 - Native clients for mobile or desktop operating systems.
 - Changes that make custom integrations easier.

## Prerequisites

At minimum, you will need a MySQL database or compatible (MariaDB that is recent)
that is at least 5.7 due to using the JSON column type. You will also need a modern
version of Python. Recommended version is 3.12 or higher due to being tested only
on this version. Finally, you will need ffmpeg installed for notification conversion.
It is heavily recommended to use a production-ready webserver for SSL termination
and static resources. Something such as nginx should be sufficient.

## Developing

CritterChat is split into two top-level components: the frontend and the backend.
The backend contains a Python server that handles all of the HTML templates, REST
endpoints and websocket implementation for talking to the frontend. It also handles
all of the persistence and provides what can be considered a fairly typical backend
server for a chat application. The frontend contains all of the JavaScript for the
client itself.

### Backend

CritterChat was designed with a Debian-like Linux OS in mind. This is not a hard
requirement and PRs that make things more generalized without breaking existing
compatibility are welcome. However, your mileage may vary if you choose a different
OS with significantly different paradigms for operation.

CritterChat's backend requires a modern version of Python 3 to operate. This was
tested on Python 3.12 but it's possible that it will run on older versions. The
entire list of Python dependencies to run the backend is in `backend/requirements.txt`.
To install them, set up a virtual environment, activate it, and then install the
requirements into it by running `python3 -m pip install -r requirements.txt`
inside the `backend/` directory.

CritterChat requires a recent version of MySQL to operate. Setting up and configuring
an empty database is outside of the scope of this documentation, but there are plenty
of guides online that will help you configure MySQL on whatever OS you choose to
run this software on. Once you've created a database that is owned by an admin
user and copied the `example/baremetal.config.yaml` example somewhere to update it with
your configuration parameters, run the following in the `backend/` directory to create
the necessary tables:

```
python3 -m critterchat.manage --config <path to your customized config> database create
```

To host a debug version of the backend server, run the following inside your
virtual environment in the `backend/` directory. You can view the instance by
opening a browser and navigating to `http://localhost:5678/`.

```
python3 -m critterchat --config <path to your customized config> --debug
```

Note that this includes debug endpoints to serve static assets, attachments, and the
like, so you don't need any other backend server to be running or to serve up the
frontend JS. Note, however, that the frontend does not come pre-compiled, so you
will want to compile a debug build of that which the debug server will serve. See
the frontend section below for how to do that.

Note also that when running with `--debug` the server will use Flask's auto-reload
feature. That means that when you save a python file or a dependency the server
will auto-reload for you so that you don't have to kill and restart it. Note that
when doing so, you may get `gevent` exception ignored errors under some circumstances.
This appears to be a minor incompatibility between the latest gevent and Flask
when using hot-reloading. This does not seem to affect the server when in production
mode.

The backend attempts to remain free of lint issues or type checking issues. To
verify that you haven't broken anything, you can run `mypy .` and `flake8 .` in
the `backend/` directory. CritterChat provides configuration for both so you don't
need to provide any other arguments. Make sure before submitting any PR that you
have run both of these and fixed any issues present.

### MySQL Schema Management

CritterChat uses SQLAlchemy's Alembic migration framework to provide schema
migrations. If you are adding or dropping a table or modifying any of the existing
tables that exist in the `backend/critterchat/data` modules you will want to
provide a schema migration that can be applied to everyone else's dev and production
instances when they pull down new code. Once you've made the desired changes to
any table definitions or added a new table in the relevant file in the
`backend/critterchat/data` directory, run the following inside the `backend/`
directory to auto-generate the schema migration that you can include in your PR:

```
python3 -m critterchat.manage --config <path to your customized config> database generate -m "<description of changes here>"
```

This will create schema migration code which automatically applies the changes
that you've made. Note that you still need to execute it against all of your
own environments including your development enviornment. To do so, run this in
the `backend/` directory:

```
python3 -m critterchat.manage --config <path to your customized config> database upgrade
```

If you change your mind or realize that the schema isn't what you want, you can
run the following to downgrade back to the previous version, make edits to the
code, delete the now-useless migration file and regenerate a fresh one. To downgrade
a migration that you just ran, run the following in the `backend/` directory:

```
python3 -m critterchat.manage --config <path to your customized config> database downgrade --tag -1
```

### Frontend

The frontend uses npm for its package management and webpack for packaging the
resulting frontend file that the backend will serve up. As a result, the dependencies
for the frontend are in the `frontend/package.json` file. Ensure you have a recent
version of npm installed and then run `npm install` to install all of the project
dependencies. There is no way to "run" the frontend per-se, as it is compiled and
served by the backend. You can build a debug version of the frontend suitable for
developing against by running the following in the `frontend/` directory:

```
npm run debug
```

This will compile everything into one file and place it in the correct spot in the
backend directory so that it can be served. It will also stamp its build hash for
automatic cache-busting. To see the effects of a new build, refresh the browser
window that you navigated to in the above backend section when you started the
debug server. As a reminder, the default is `http://localhost:5678/`.

CritterChat attempts to stay clean of any lint errors. To verify that you haven't
introduced any issues, you can run `npm run lint` in the `frontend/` directory.
Make sure to run this before submitting any PR, and ensure that you've cleaned
up any warnings or errors that are called out. Note that every time you build
a new build, the resulting artifacts will be copied to the
`backend/critterchat/http/static/` directory. This can start getting messy after
awhile due to the build hash changing every time you make an update. You can
clean this up by running `npm run clean` in the `frontend/` directory. Note that
this will delete all builds, including the last one, so you will often want to
follow up by rebuilding for debug or production.

When you're ready to deploy to a production instance, you will obviously want a
minified and optimized version of the frontend. To get that, first you'll want
to clean old builds by running `npm run clean` in the `frontend/` directory. If
you forget this step it won't result in an old version being served to clients
but it will leave extra files laying around. Then, run `npm run build` in the
same `frontend/` directory.

### Submitting a PR

CritterChat welcomes contributors! Open source software would not work if each
project only had one maintainer. Make sure that you've tested your changes,
ensure that the backend is typing and lint clean, and ensure the frontend is
lint clean. Then, submit a PR to this repo with a description of what you're
modifying, how you tested it, and what you wanted to accomplish with this PR.
If you are adding new UX or changing something around visually it can help to
include before and after screenshots. It can also help to describe the intended
user interactions with your new feature.

## Running in Production

CritterChat uses nginx for SSL termination as well as static resources server
for production instances. While it is possible to run an instance without nginx,
it is not recommended. Offloading static assets takes load off of the server
itself so that it can concentrate on dynamic requests from clients. Additionally,
no support for SSL is included in the default software so you would end up running
with plain http which exposes all chat messages and user login details to the
public internet.

In the `example/` directory you'll find a systemd service file for the backend
as well as an nginx configuration file for the nginx proxy portion. Both are meant
to be customized for your domain and certs, as well as where you ultimately decide
to deploy CritterChat for a production instance. For SSL certificates, I recommend
using `certbot` which is a CLI interface to the Let's Encrypt project. If you want
to purchase certificates and use them in your nginx config instead you can.

### Initial Setup

Initial setup is fairly straightforward. Pick a directory that you will deploy to,
create it, and make sure that it is owned by the user that will execute the server.
Make sure that it is readable by the user that nginx uses since it will serve
static assets out of this directory as well. Copy `example/baremetal.config.yaml`
to the directory you've just created and make sure that you customize it for your
installation. Create an attachments directory under the installation directory and
again make sure that it is owned by the server user and readable by the nginx
user.

Review your config.yaml to ensure that you've modified everything you need to.
Ensure that the `database` section points at your production database. Make sure
that the `cookie_key`, `password_key` and `attachment_key` are all set to a
random string of sufficient length. I recommend keeping them different and using
a random generator that can give you a string of at least 48 characters. Note that
it is important to select good random values now and not change them in the future.
Changing these values in a production instance can have undesirable effects. If
you change the `cookie_key` in a production instance, all sessions will be logged
out. If you change `password_key` in production, all passwords will be invalidated
and you will have to manually change all of them. If you change `attachment_key`
in a production instance, all existing attachments will 404. So, choose good values
when setting up your instance and do not modify them. Make sure you rename your
instance to what you want to call it. Finally, configure the attachment system.
Right now, only local storage is supported, so leave it set to local, and leave
the prefix as-is. Update the directory to the absolute path of the attachment
directory you created above.

Now that your config is updated, create a Python virtual environment for the
production installation. I recommend sticking it in the deployed folder under a
directory called `venv` or similar. It doesn't matter where it is, but you'll
want to keep organized. Once you've created that virtual environment you'll
be activating it every time you want to install updates. For now, activate it
and install the initial production instance by going into the `backend/`
directory and running `python3 -m pip install .`. This will install all dependencies,
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
traffic. Make a copy of the `example/critterchat-nginx-conf` file and place it
into `/etc/nginx/sites-available`. Edit the `server_name` line everywhere it appears
and change it to the domain that you are running this under. Don't forget to edit
the `return` line in the top portion of the file to auto-promote non-SSL traffic
to SSL. Update the SSL certificate lines near the top and in the location directives
to point at your SSL certificates you obtained through `certbot` or through
purchasing certificates. Update all `proxy_pass` lines and ensure that the port
listed there is the same one that you chose in your systemd service configuration
above. Update the `alias` line under the `/attachments` location to point to the
same absolute path you configured for your attachments in your config.yaml. Update
the `alias` line under the `/static` location prefix to the same absolute path
you created for your venv. Take careful note to only edit the portion before the
`/lib` as the rest of that directory is where installing the backend will put
static resources.

Now, once this is done, symlink the file you just created into `/etc/nginx/sites-enabled`
to activate this and restart nginx using `systemctl restart nginx`. Once
the restart is complete, you should have a production instance of CritterChat running
on the domain you've chosen!

### Administration

Most of the administration for the server can be done in the CLI. At some point
I would like to be able to administer through the web interface as well but this
has not been implemented yet. The main administration interface can be found by
activating the production virtual environment and then running the following:

```
python3 -m critterchat.manage --help
```

This includes a bunch of stuff for adding and removing custom emojis, adding users,
activating and deactivating existing users, changing a user's password, creating
public rooms, and managing the auto-join setting for public rooms. In the future
it will include a host of other helpful utilities. At the moment the software is
hardcoded to allow open signups but leave users not activated. You can find users
to activate by running the following command:

```
python3 -m critterchat.manage --config <path to your production config> user list
```

You can then activate them using a similar command:

```
python3 -m critterchat.manage --config <path to your production config> user activate -u <username>
```

Right now there are virtually no moderator tools. If somebody gets too unruly or
spicy, you can deactivate their account using the following command. This will log
them out of all interfaces they're logged in on and prevent them from logging back
in again.


```
python3 -m critterchat.manage --config <path to your production config> user deactivate -u <username>
```

### Upgrading Production

Once you've got everything installed, if you want to apply updates that you've
pulled from anything checked in, you can do so with the following steps. First,
actually pull the changes by refreshing your git repository. Go into the `frontend/`
directory and make sure you've built a new production bundle by running
`npm run clean && npm run build`. Then, activate the virtual environment you
created for the production instance. Now, stop the running server by executing
`systemctl stop critterchat`. Now, in the `backend/` directory, run
`python3 -m pip install --upgrade .` to upgrade dependencies and install the new
version of CritterChat. Then run to following command to upgrade your database
schema to match the new code:

```
python3 -m critterchat.manage --config <path to your production config> database upgrade
```

Finally, once all those steps are done, re-start the backend service with
`systemctl start critterchat`. If all went according to plan you should have the
new version running on your instance. Users that are currently logged in should get
a new update notification banner, and you can refresh the page to load the new version.

## Docker Hosting

### Getting Started

To launch the default settings, simply clone the repo and navigate to `./critterchat-docker`, then run:
```
docker compose up -d
```
to launch the app. This uses the config in the `critterchat-docker` folder called `docker.config.yaml` and provides bind mounts for the mysql database as well as the attachments folder. After making a change to the configuration, run:
```
docker compose restart
```
to reload the instance and load the new settings.

### Administration

Administration tools and other CLI interfaces can be accessed using:
```
docker exec -it CritterChat /bin/sh
```
which will drop you to a shell inside the container.

### Upgrading

This has not been tested thoroughly, but should not cause any data loss since the database and attachments are kept in a bind mount. In theory it should be as simple as:
```
docker compose down
git pull
docker image rm critterchat-docker-backend:latest
docker compose up -d
```
to pull the new code and relaunch it.
