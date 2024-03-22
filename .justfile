
alias bd := build-docs
alias sd := show-docs

default:
    @just --list

# Run all tests
test:
    cd {{justfile_directory()}}; . .venv/bin/activate; pytest tests

# Build documentation
build-docs:
    cd {{justfile_directory()}}/documentation; . .venv/bin/activate; ./builddocs.sh

# Show documentation in browser
show-docs:
    python -m webbrowser "file://{{justfile_directory()}}/documentation/build/html/index.html"


