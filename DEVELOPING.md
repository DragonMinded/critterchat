# Developing

CritterChat is split into two top-level components: the frontend and the backend.
The backend contains a Python server that handles all of the HTML templates, REST
endpoints and websocket implementation for talking to the frontend. It also handles
all of the persistence and provides what can be considered a fairly typical backend
server for a chat application. The frontend contains all of the JavaScript for the
client itself.

This readme walks through how to set yourself up for development on both the
frontend and backend using a self-managed Python venv and manually invoking various
tools from the command-line in the correct directory (either `frontend/` or
`backend/` depending). If you want to jump past that and use a semi-managed
development environment, skip to the "Convenience Scripts" section below.

## Backend

CritterChat was designed with a Debian-like Linux OS in mind. This is not a hard
requirement and PRs that make things more generalized without breaking existing
compatibility are welcome. However, your mileage may vary if you choose a different
OS with significantly different paradigms for operation.

CritterChat's backend requires a modern version of Python 3 to operate. This was
tested on Python 3.12 but it's possible that it will run on older versions. The
entire list of Python dependencies to run the backend is in `backend/requirements.txt`.
To install them, set up a virtual environment somewhere, activate it, and then
install the requirements into it by running `python3 -m pip install -r requirements.txt`
from inside the `backend/` directory.

CritterChat requires either SQLite (which comes with Python) or a recent version of
MySQL to operate. If you are planning on doing serious development it is recommended
to go with MySQL because you will be set up to run the database tests against both it
and SQLite before submitting changes upstream. Setting up and configuring an empty
MySQL database is outside of the scope of this documentation, but there are plenty
of guides online that will help you configure MySQL on whatever OS you choose to
run this software on. Once you've created a database that is owned by a specific DB
user and copied the `example/baremetal.mysql.config.yaml` example somewhere to update
it with your configuration parameters, run the following in the `backend/` directory
with your virtual environment active to create the necessary tables:

```
python3 -m critterchat.manage --config <path to your customized config> database create
```

To host a debug version of the backend server, run the following while your virtual
environment is active in the `backend/` directory. You can view the instance by
opening a browser and navigating to `http://localhost:5678/`.

```
python3 -m critterchat --config <path to your customized config> --debug
```

Note that this includes debug endpoints to serve static assets, attachments, and the
like, so you don't need any other backend server to be running or to serve up the
frontend JS. Note, however, that the frontend does not come pre-compiled so you
will want to compile a debug build of that which the debug server will serve. See
the frontend section below for how to do that.

Note also that when running with `--debug` the server will use Flask's auto-reload
feature. That means that when you save a python file or a dependency the server
will auto-reload for you so that you don't have to kill and restart it. Note that
when doing so, you may get `gevent` exception ignored errors under some circumstances.
This appears to be a minor incompatibility between the latest gevent and Flask
when using hot-reloading. This does not affect the server when in production mode.

The backend attempts to remain free of lint issues and type checking issues. To
verify that you haven't broken anything, you can run `mypy .` and `flake8 .` in
the `backend/` directory while your virtual environment is active. CritterChat
provides configuration for both so you don't need to provide any other arguments.
Make sure before submitting any PR that you have run both of these and fixed any
issues present.

The backend also includes its own test suite, run by pytest. To run all tests in the
backend you can run `pytest` in the `backend/` directory with your virtual environment
active much like you would the above lint and type checking commands. By default,
there is no test database set up so all tests that require a testing MySQL instance
to operate will auto-skip. If you want to run the DB tests to verify or iterate on
the various `critterchat.data` modules you will want to set up a testing DB in your
MySQL instance. Create an empty database in an identical fashion to how you created
your local development DB above. Then, create a `.testdb.toml` under the
`backend/tests/` directory with the following contents and customize it to your
testing DB credentials. Note that every time the tests run, this DB will be wiped
and recreated fresh so do not use your local development or production DB for this.

```
[database]
address = "localhost"
database = "critterchat_test"
user = "critterchat_test"
password = "critterchat_test"
```

Note that all tests in the backend should be tagged as either `unit` or `integration`
so that somebody wishing to iterate quickly can run only one type of test. This is
enforced by the test configuration but you can easily mark a test or a class of tests
using either the `@pytest.mark.unit` or `@pytest.mark.integration` decorator.

## Schema Management

CritterChat uses SQLAlchemy's Alembic migration framework to provide schema
migrations. If you are adding or dropping a table or modifying any of the existing
tables that exist in the `backend/critterchat/data/` modules you will want to
provide a schema migration that can be applied to everyone else's dev and production
instances when they pull down new code. Once you've made the desired changes to
any table definitions or added a new table in the relevant file in the
`backend/critterchat/data/` directory, run the following inside the `backend/`
directory with your virtual environment active to auto-generate the schema migration
that you can include in your PR:

```
python3 -m critterchat.manage --config <path to your customized config> database generate -m "<description of changes here>"
```

This will create schema migration code which automatically applies the changes
that you've made which should work for both MySQL and SQLite. Note that you still
need to execute it against all of your own environments including your development
enviornment. To do so, run this in the `backend/` directory with your virtual
environment active:

```
python3 -m critterchat.manage --config <path to your customized config> database upgrade
```

If you change your mind or realize that the schema isn't what you want, you can
run the following to downgrade back to the previous version, make edits to the
code, delete the now-useless migration file and regenerate a fresh one. To downgrade
a migration that you just ran, run the following in the `backend/` directory with
your virtual enviornment active:

```
python3 -m critterchat.manage --config <path to your customized config> database downgrade --tag -1
```

## Frontend

The frontend uses npm for its package management and webpack for packaging the
resulting frontend file that the backend will serve up. As a result, the dependencies
for the frontend are in the `frontend/package.json` file. Ensure you have a recent
version of npm installed and then run `npm install` from the `frontend/` directory
to install all of the project dependencies. There is no way to "run" the frontend
per-se, as it is compiled and served by the backend. You can build a debug version
of the frontend suitable for developing against by running the following in the
`frontend/` directory:

```
npm run debug
```

This will compile everything into one file and place it in the correct spot in the
backend directory so that it can be served. It will also stamp a build hash for
automatic cache-busting. To see the effects of a new build, refresh the browser
window that you navigated to in the above backend section when you started the
debug server. As a reminder, the default is [http://localhost:5678/](http://localhost:5678/).

CritterChat attempts to stay clean of any lint errors. To verify that you haven't
introduced any issues, you can run `npm run lint` in the `frontend/` directory.
It also attempts to keep all tests passing. To verify you haven't broken anything
under test, you can similarly run `npm run test` in the `frontend/` directory.
Make sure to run both before submitting any PR and ensure that you've cleaned
up any warnings or errors that are called out. Note that every time you build
a new build, the resulting artifacts will be copied to the
`backend/critterchat/http/static/` directory. This can start getting messy after
awhile due to the build hash changing every time you make an update. You can
clean this up by running `npm run clean` in the `frontend/` directory. Note that
this will delete all builds including the current one, so you will often want to
follow up by rebuilding for debug or production.

When you're ready to deploy to a production instance, you will generally want a
minified and optimized version of the frontend. To get that, first you'll want
to clean old builds by running `npm run clean` in the `frontend/` directory. If
you forget this step it won't result in an old version being served to clients
but it will leave extra files laying around. Then, run `npm run build` in the
same `frontend/` directory.

## Convenience Scripts

CritterChat uses `just` as a command runner to give developers a convenient way
to remember common actions when developing. This is purely optional, but if you
want to use the commands that are saved in the repo you can install the `just`
command runner tool by following the instructions on [the just repo](https://github.com/casey/just#installation).
Various available commands are documented here.

Many just commands which run backend operations require a configuration file
for your database setup and other local development server config. Make a copy
of the example bare metal file by running `just init` and then edit the copy
which has been placed in `backend/.config.yaml`. This config will be used by
all of the backend just commands that need a config.

```
just setup
```

Creates or updates a `.venv` directory in the backend which is used for all
other backend-related commands. Installs all needed python dependencies into
that `.venv` directory. Then, runs the npm install process in the frontend.
The result of running `just setup` is that you should have a locally-configured
enviroinment to run a debug version of CritterChat as well as the various test
and lint utilities.

```
just manage
```

Invoke the backend instance management utility using the config file for development.
You can use this to perform any management operations, such as `just manage user list`
to list all users in the development instance you're operating on. You can also run
like `just manage --help` to see the instance management utility's help. If you
have used just to set up your local environment from scratch, don't forget to run
`just manage database create` before any other manage or run commands to ensure
that your DB is fully set up.

```
just run
```

Ensures that the frontend is compiled for debug and then starts a development
server that can be reached at [http://localhost:5678/](http://localhost:5678/).
Reads configuration from `backend/.config.yaml` which you should have either
copied manually or edited after running `just init`. That configuration should
point at your local database and have your customizations for various server options.

```
just lint
```

Runs all lint and type-checking verifications against both the backend and frontend.
Halts after the first group of errors found and prints everything wrong at that point.

```
just test
```

Runs all tests against both the backend and frontend. Halts after the first
group of test failures found and prints everything wrong at that point.

## Submitting a PR

CritterChat welcomes contributors! Open source software would not work if each
project only had one maintainer. Make sure that you've tested your changes, ensure
that the backend is typing, lint and test clean, and ensure the frontend is lint and
test clean. Then, submit a PR to this repo with a description of what you're
modifying, how you tested it, and what outcomes the changes should provide.
If you are adding new UX or changing something around visually it can help to
include before and after screenshots. It can also help to describe the intended
user interactions with your new feature.

If you are going to take a stab at a larger feature please open a discussion as
a GitHub issue first. There's nothing worse than finding out after the fact that
your hard work can't be merged for whatever reason. Please be collaborative with
the maintainers from the beginning to ensure the greatest chance of success with
the least amount of wasted effort.

Note that this repository does not accept generative AI contributions. If you are
not going to do the work yourself, please do not attempt to open a PR. Not only
is this highly unethical and can not be copyrighted but there's a high chance
you didn't actually review the code, leading to an additional burden on the
maintainers of CritterChat.
