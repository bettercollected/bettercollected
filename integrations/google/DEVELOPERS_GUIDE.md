# Developers Guide
This document explains the development guide to the new users participating in the development of the project.

### IMPORTANT NOTE: Before committing the files, follow the below instructions
1. After the required packages are installed, i.e., `pip install -r requirements.txt`; run `pre-commit install` command to enable autoformatting and linting checks.
2. Run `pre-commit autoupdate`, this will update the mutable references.
3. When running `git commit` command, use terminal instead of IDE commit feature as we'll see errors if the commit fails because of autoformatting or some other reason and we can fix it and re-commit.

### Configurations
1. After running the above command upto `Step 2`, few configurations like `flake8` and `black` are installed and configured. The plugins check the code quality and formatting. To run these checks, you can simply run `make format`. **Note: you might need to install `make`.**
2. Copy [.env.example](.env.example) file, rename it to `.env`, and add appropriate environment variables there. **[NOTE: If any new environment variable is added to the project, do not forget to add it in `.env.example` file as well]**

### Add required environment variables
| API Environment                 | Default value                                   |
|---------------------------------|-------------------------------------------------|
| API_ENVIRONMENT                 | development                                     |
| API_ORGANIZATION_NAME           | BetterCollected                                 |
| API_TITLE                       | "Better Collected API"                          |
| API_DESCRIPTION                 | "Rest endpoints for bettercollected schedulers" |
| API_VERSION                     | 1.0.0                                           |
| API_ALLOWED_ORIGINS             | http://localhost:3000,http://localhost:8000     |
| API_HOST                        | http://localhost:8000                           |
| API_KEY_ID_LENGTH               | 35                                              |
| API_KEY_PASSWORD_LENGTH         | 20                                              |
| API_KEYPREFIX                   ||
| API_JWT_SECRET                  ||
| API_ACCESS_TOKEN_EXPIRY_MINUTES | 60                                              |
| API_REFRESH_TOKEN_EXPIRY_DAYS   | 30                                              |
| API_CLIENT_REDIRECT_URI         | http://localhost:3000                           |
| API_SERVERS                     ||
| API_ROOT_PATH                   ||
| API_DOCS_PATH                   ||
| API_REDOC_PATH                  ||
| API_OPENAPI_PATH                ||
| API_ROOT_PATH_IN_SERVERS        | False                                           |
| API_KEY_PREFIX                  | better_collected_                               |
| API_SCHEDULER_TIME_IN_SECONDS   | 30                                              |

| Google Environment                 | Default value                                    |
|------------------------------------|--------------------------------------------------|
| GOOGLE_CLIENT_TYPE                 | web                                              |
| GOOGLE_CLIENT_ID                   ||
| GOOGLE_PROJECT_ID                  ||
| GOOGLE_AUTH_URI                    | https://accounts.google.com/o/oauth2/auth        |
| GOOGLE_TOKEN_URI                   | https://oauth2.googleapis.com/token              |
| GOOGLE_AUTH_PROVIDER_X509_CERT_URL | https://www.googleapis.com/oauth2/v1/certs       |
| GOOGLE_CLIENT_SECRET               ||
| GOOGLE_REDIRECT_URIS               | http://localhost:8000/auth/google/oauth2callback |
| GOOGLE_JAVASCRIPT_ORIGINS          | http://localhost:3000                            |
| GOOGLE_SCOPES                      ||
| GOOGLE_API_SERVICE_NAME            | drive                                            |
| GOOGLE_API_VERSION                 | v2                                               |
| GOOGLE_REVOKE_CREDENTIALS_URL      | https://oauth2.googleapis.com/revoke             |
| GOOGLE_AES_KEY                     ||

| Mongo DB Environment | Default value |
|----------------------|---------------|
| MONGO_DB             ||
| MONGO_URI            ||


### Write test cases
Write tests with `pytest` or some other, whichever you feel comfortable with. **Might need to configure for tests other than pytest.**

### Directory structure
1. [common](common) - is a submodule.
2. [dependencies](dependencies) - contains all the dependency injections of the app.
3. [handlers](handlers) - contains all the handlers, e.g., cors, database connection, etc.
4. [middlewares](middlewares) - contains all the middlewares.
5. [repositories](repositories) - contains codebase that interacts with the database.
6. [routers](routers) - contains all the routes of the application.
7. [services](services) - contains all the business logic of the application.
8. [settings](settings) - contains all the settings of the application.
9. [tests](tests) - contains all the test cases.

**_Add/update comments and docstring if you are editing the codebase._**

**_If you are a contributor, make smaller pull requests based on the issues created._**
