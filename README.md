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
 - Custom emoji support controlled by the instance administrator.

## Wishlist

 - Message editing.
 - Message deleting.
 - Message reactions.
 - Reply to message.
 - Now typing indicators.
 - Read receipts.
 - Pinned messages.
 - Moderation tools for network admin (global mute, global ban, etc).
 - Moderation tools for individuals (block user, allow messages, allow in search, etc.).
 - Sign-up modes (admin approval, open sign-ups, invite only, etc.).
 - Emoji auto-categorization by prefix.
 - Photo attachments, both uploaded and pasted from clipboard.
 - Arbitrary file attachments.
 - Sitewide CSS themeing with CSS moved to themes directory.
 - Per-chat CSS themeing for direct messages and rooms.
 - Ability to set a personal nickname for a user that only you can see.
 - Port Myno's Pictochat over from PyStreaming, allow drawing and remixing.
 - Link auto-sanitization to remove tracking info.
 - Multi-account support.
 - Inter-instance direct message and room support.

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
user and copied the `backend/config.yaml` example somewhere to update it with your
configuration parameters, run the following in the `backend/` directory to create
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
