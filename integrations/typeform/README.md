### Running the project

**NOTE: Latest codebase is in develop branch**

1. Install `pyenv` with `python` version `3.10` . And activate a virtual environment.
2. Look into [Makefile](Makefile) to see if you might need any command. If you need additional commands, you can add it there.
3. Run `make install`, this will install `poetry` by default if it's not installed.
4. Check if virtualenv made by poetry is of python version `3.10` or not by using command `poetry run python --version`. 
5. If it is not of python version `3.10` then  create a new virtualenv using command `poetry env use 3.10.x`.
6. Copy [.env.example](.env.example) with the name `.env`, and add/update the environment variables there. (**Note: Keep `AUTH_JWT_SECRET` values same through every project for bettercollected**)
7. Then open virtualenv using command `poetry shell`.
8. After configuring the environment variables, the application is ready to run
9. Run `uvicorn typeform.app:get_application --port 8002 --reload --env-file .env`

### Contributing

1. Create a pull request for any issue into `develop` branch at first.
2. Run `pre-commit install` and `pre-commit autoupdate`.
3. Run `make format` command to format the codebase.
4. Run `make flake8` and fix up the flake issues.
5. Run `make test` to run all the tests.
6. Run `make coverage` to run code coverage.
