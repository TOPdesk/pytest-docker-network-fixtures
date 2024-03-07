
alias bd := build-docs
alias sd := show-docs

default:
    @just --list

build-docs:
    cd {{justfile_directory()}}/documentation; . .venv/bin/activate; ./builddocs.sh

show-docs:
    python -m webbrowser "file://{{justfile_directory()}}/documentation/build/html/index.html"


