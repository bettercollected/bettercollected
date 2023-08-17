# Common / Shared files
_**NOTE: This project only contains shared data and files, so there is no starting point of the application in this repository.**_

This repository contains only the shared files that are used in other repositories. If in case you need to update this repository, please follow the instructions below:

### Steps to edit the project
1. The python version: `3.10`, so a python version manager is a good choice for maintaining different version of python and different environments. <br/> [PyEnv](https://github.com/pyenv/pyenv) and [PyEnv VirtualEnv](https://github.com/pyenv/pyenv-virtualenv)
2. Activate the `virtualenv` and install the required packages from [requirements.txt](requirements.txt) with `pip install -r requirements.txt`.
3. Make changes or add new files as you need.

### NOTE: Before committing the files, follow the below instructions
1. After the required packages are installed, i.e., `pip install -r requirements.txt`; run `pre-commit install` command to enable autoformatting and linting checks.
2. Run `pre-commit autoupdate`, this will update the mutable references.
3. When running `git commit` command, use terminal instead of IDE commit feature as we'll see errors if the commit fails because of autoformatting or some other reason and we can fix it and re-commit.

### Directory structure
1. [configs](configs) consist the configurations.
2. [constants](constants) consist the global constants.
3. [enums](enums) consist all the application enums.
4. [exceptions](exceptions) consist custom exception classes.
5. [models](models) consist all the models.
6. [schemas](schemas) consist all the schemas.
7. [utils](utils) consist different utility functions.
