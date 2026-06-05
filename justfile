set positional-arguments

# Initialize backend config by copying from example directory
init backend="sqlite":
    cp example/baremetal.{{backend}}.config.yaml backend/.config.yaml
    cp example/baremetal-info.txt backend/.info.txt
    sed -i 's/baremetal-info.txt/.info.txt/g' backend/.config.yaml

# Set up both backend and frontend package management to run locally
setup:
    cd backend && python3 -m venv .venv
    ./backend/.venv/bin/python3 -m pip install --upgrade pip -r backend/requirements.txt
    cd frontend && npm install

# Build a debug version of the frontend package
build:
    cd frontend && npm run debug

# Build everything that needs to be built and then run critterchat using config from init
run *ARGS: build
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
