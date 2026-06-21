set positional-arguments

# Initialize backend config by copying from example directory
init backend="sqlite":
    cp example/baremetal.{{backend}}.config.yaml backend/.config.yaml
    cp example/baremetal-info.txt backend/.info.txt
    sed -i 's/"baremetal-info.txt"/".info.txt"/g' backend/.config.yaml
    sed -i 's/"sqlite.db"/".sqlite.db"/g' backend/.config.yaml

# Set up both backend and frontend package management to run locally
setup:
    cd backend && python3 -m venv .venv
    ./backend/.venv/bin/python3 -m pip install --upgrade pip
    ./backend/.venv/bin/python3 -m pip install --upgrade -r backend/requirements.txt
    ./backend/.venv/bin/python3 -m pip install --upgrade -r backend/requirements-dev.txt
    cd frontend && npm install

# Build a batteries-included package of critterchat that can be uploaded to pypi
build:
    cd frontend && npm run clean && npm run build
    cd backend && rm -rf build/ dist/
    cp README.md LICENSE backend/
    cd backend/critterchat/manage && rm -rf example
    cp -r example backend/critterchat/manage/
    cd backend && sed -i '/## Quick Start Guide/,$d' README.md && cat QUICKSTART.md >> README.md
    cd backend && ./.venv/bin/python3 -m build --no-isolation --quiet
    rm -rf backend/README.md backend/LICENSE
    rm -rf backend/critterchat/manage/example

# Release a version of the critterchat package to pypi
release:
    cd backend && ./.venv/bin/python3 -m twine upload dist/*

# Build everything that needs to be built and then run critterchat using config from init
run *ARGS:
    cd frontend && npm run debug
    cd backend && ./.venv/bin/python3 -m critterchat --config .config.yaml --debug "$@"

# Run critterchat.manage using config from init
manage *ARGS:
    cd backend && ./.venv/bin/python3 -m critterchat.manage --config .config.yaml "$@" 

# Run all frontend and backend linting tools
lint:
    cd backend && ./.venv/bin/flake8 .
    cd backend && ./.venv/bin/mypy .
    cd frontend && npm run lint

# Run all frontend and backend tests
test:
    cd backend && ./.venv/bin/python3 -m pytest
    cd frontend && npm run test

# Run backend tests with coverage enabled and report on test coverage
coverage module="critterchat" tests="tests/":
    cd backend && ./.venv/bin/python3 -m pytest --cov={{module}} --cov-report=term-missing {{tests}}
