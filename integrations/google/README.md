# Google Forms Integration Repository
**_Contains a git submodule `common`_**

This repository contains only the Google forms API integration logic. If in case you need to update this repository, please follow the instructions below:

### Steps to run the project
1. The python version: `3.10`, so a python version manager is a good choice for maintaining different version of python and different environments. <br/> [PyEnv](https://github.com/pyenv/pyenv) and [PyEnv VirtualEnv](https://github.com/pyenv/pyenv-virtualenv)
2. Activate the `virtualenv` and install the required packages from [requirements.txt](requirements.txt) with `pip install -r requirements.txt`.
3. **TODO other steps pending.**

### Steps to keep submodules in sync
1. Run the command: `git submodule sync --recursive`.
2. Update the submodule changes to your local: `git submodule update --recursive`.
3. You may need to go into `submodule` directory and checkout to appropriate branch before continuing, `git checkout master`.

### NOTE: Before committing the files, follow the below instructions
1. After the required packages are installed, i.e., `pip install -r requirements.txt`; run `pre-commit install` command to enable autoformatting and linting checks.
2. Run `pre-commit autoupdate`, this will update the mutable references.
3. When running `git commit` command, use terminal instead of IDE commit feature as we'll see errors if the commit fails because of autoformatting or some other reason and we can fix it and re-commit.
