# Common / Shared files

_**NOTE: This project only contains shared data and files, so there is no starting point of the application in this repository.**_

This repository contains only the shared files that are used in other repositories. If in case you need to update this repository, please follow the instructions below:

### Steps to edit the project

1. The python version: `3.10+`, [uv](https://github.com/astral-sh/uv) is recommended for managing the environment.
2. Run `uv sync` to install the required packages and create a virtual environment.
3. Activate the environment with `source .venv/bin/activate`.
4. Make changes or add new files as you need.

### NOTE: Before committing the files, follow the below instructions

1. Run `uv run pre-commit install` command to enable autoformatting and linting checks.
2. Run `uv run pre-commit autoupdate`, this will update the mutable references.
3. When running `git commit` command, use terminal instead of IDE commit feature as we'll see errors if the commit fails because of autoformatting or some other reason and we can fix it and re-commit.

### Directory structure

1. [configs](common/configs) consist the configurations.
2. [constants](common/constants) consist the global constants.
3. [enums](common/enums) consist all the application enums.
4. [exceptions](common/exceptions) consist custom exception classes.
5. [models](common/models) consist all the models.
6. [schemas](common/schemas) consist all the schemas.
7. [utils](common/utils) consist different utility functions.
