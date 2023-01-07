# Google Forms Integration Repository
**_Contains a git submodule `common`_**

This repository contains only the Google forms API integration logic. If in case you need to update this repository, please follow the instructions below:

### Steps to run the project
1. The python version: `3.10`, so a python version manager is a good choice for maintaining different version of python and different environments. <br/> [PyEnv](https://github.com/pyenv/pyenv) and [PyEnv VirtualEnv](https://github.com/pyenv/pyenv-virtualenv)
2. Activate the `virtualenv` and install the required packages from [requirements.txt](requirements.txt) with `pip install -r requirements.txt`.
3. Read all the below instructions carefully and please follow our [DEVELOPERS_GUIDE](DEVELOPERS_GUIDE.md).

    #### Steps to keep submodules in sync
   1. Initialize submodule: `git submodule init`.
   2. Run the command: `git submodule sync --recursive`.
   3. Update the submodule changes to your local: `git submodule update --recursive`.
   4. You may need to go into `submodule` directory and checkout to appropriate branch before continuing, `git checkout master`.

    #### IMPORTANT NOTE
    After updating the `submodule` you need to install that submodule as a dependency. Locally, you can do it with: 
    `pip install ./common`.
