set positional-arguments

init:
    cp example/baremetal.config.yaml backend/.config.yaml
    cp example/baremetal-info.txt backend/.info.txt
    sed -i 's/baremetal-info.txt/.info.txt/g' backend/.config.yaml

setup:
    cd backend && python3 -m venv .venv
    ./backend/.venv/bin/python3 -m pip install --upgrade pip -r backend/requirements.txt
    cd frontend && npm install

build:
    cd frontend && npm run debug

run: build
    cd backend && ./.venv/bin/python3 -m critterchat --config .config.yaml --debug

manage *ARGS:
    cd backend && ./.venv/bin/python3 -m critterchat.manage --config .config.yaml "$@" 

lint:
    cd backend && ./.venv/bin/flake8 .
    cd backend && ./.venv/bin/mypy .
    cd frontend && npm run lint

test:
    cd backend && ./.venv/bin/python3 -m pytest
    cd frontend && npm run test
