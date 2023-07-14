# Better Collected

Source code for Better Collected, with Next.js version `12.3.1`.

<hr/>

## Prerequisites

These are some of the required tools or process that you need to follow in order to run the application.

1. Install Docker on your machine. [Installation Link](https://docs.docker.com/get-docker/).
2. Generate a Google client secret. To generate a Google client secret in a new project, you need to follow these steps:
    1. Go to the [Google Cloud Console](https://console.cloud.google.com/) and sign in to your account.
    2. Create a new project by clicking on the dropdown menu at the top of the screen and selecting "New Project".
    3. Enter a name for your project and click on the "Create" button.
    4. Once your project is created, select it from the dropdown menu at the top of the screen.
    5. In the left sidebar, click on the "APIs & Services" option.
    6. Click on the "Enabled APIs & Services", and enable "Google Forms API" and "Google Drive API".
    7. Click on the "Credentials" tab.
    8. Click on the "Create Credentials" button and select "OAuth client ID" from the dropdown menu.
    9. Select "Web App" as the application type and enter a name for your OAuth client ID.
    10. Add two Redirect URIs: `http://localhost:8000/api/v1/auth/google/basic/callback` and `http://localhost:8000/api/v1/auth/google/oauth/callback`. Also, add three JavaScript origins: `http://localhost:3000`, `http://localhost:3001`, and `http://localhost:3002`.
    11. Click on the "Create" button.
    12. Click on the "OAuth consent screen". From here, you can add new test users and add different scopes. The required scopes for our application to run are: `auth/userinfo.email`, `auth/userinfo.profile`, `openid`, `auth/forms.body.readonly`, `auth/forms.responses.readonly`, and `auth/drive.metadata.readonly`.
    13. In the "OAuth client ID" page, you can find your client ID and client secret.
    14. Click on the "Download" button to download your client secret as a JSON file.
        Once you have generated your client secret, you can use it in your application to authenticate with Google APIs.
3. Generate a Typeform client secret. To generate a Typeform client secret, you need to follow these steps:
    1. Go to the [Admin Typeform's Developer Apps](https://admin.typeform.com/).
    2. Go to Developer apps from the dashboard and "Register a new app".
    3. Fill up the details and set the "Redirect URIs": `http://localhost:8000/api/v1/auth/typeform/basic/callback` and `https://localhost:8000/api/v1/auth/typeform/oauth/callback`.
    4. Once you register the new app, you'll see a `secret`. You need to save this secret some place safe as you'll not see this again.
    5. You can see the `client_id` whenever you want to.

<hr/>

## Usage

Here are the steps you need to take to run the **BetterCollected** project.

#### A. Clone the repo

The need for you to clone this repository is because you need it to seed the data inside MongoDB. Or, you can copy [Dockerfile.mongo-seed](Dockerfile.mongo-seed), [seed-data.js](seed-data.js), and [nginx.conf](nginx.conf) files from this repo and save it locally on your device at the same directory level where you'll place your `docker-compose.yml` file, and update the `nginx.conf` file with `http://webapp:3000` to `http://localhost:3000`.

#### B. Configure common docker-compose environments that are same in all the services used

1. Generate a Fernet key or use the provided one in the services environment example itself. The Fernet key must be a base64-encoded 32-byte key. [See how to generate fernet key](https://airflow.apache.org/docs/apache-airflow/stable/administration-and-deployment/security/secrets/fernet.html). Or, install `cryptography` package in python and print out the `fernet_key` and use it where necessary. **Note:** The generated fernet key must be same in the entire service environment where applicable.

    - Environment name used in `backend` service: `AUTH_AES_HEX_KEY`
    - Environment name used in `auth` service: `AUTH_AES_HEX_KEY`
    - Environment name used in `integrations-googleform` service: `GOOGLE_AES_KEY`

    ```py
    from cryptography.fernet import Fernet

    fernet_key = Fernet.generate_key()
    print(fernet_key.decode())  # your fernet_key, keep it in secured place!
    ```

2. Generate a JWT secret. This can be any random value that is 32 characters, or you can use the provided one in the services environment example itself. [See how to get random keys, you can use 256-bit key from CodeIgnitor Encryption Keys section](https://randomkeygen.com/). **Note:** The JWT secret must be same in the entire service environment where applicable.

    - Environment name used in `backend` service: `AUTH_JWT_SECRET`
    - Environment name used in `auth` service: `AUTH_JWT_SECRET`
    - Environment name used in `integrations-typeform` service: `AUTH_JWT_SECRET`
    - Environment name used in `integrations-googleform` service: `AUTH_JWT_SECRET`

3. After you created the `Google` secret. You need to add the values from the secret into our docker-compose environments

    - Environment name used in `auth` service and `integrations-googleform` service: `GOOGLE_CLIENT_ID`, `GOOGLE_PROJECT_ID`, and `GOOGLE_CLIENT_SECRET`

4. After you created the `Typeform` secret. You need to add the values from the secret into our docker-compose environments
    - Environment name used in `auth` service and `integrations-typeform` service: `TYPEFORM_CLIENT_ID` and `TYPEFORM_CLIENT_SECRET`

#### C. Configure `backend` service's environment in docker-compose

1. Add `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` in the `backend` service from boto3 client (wasabi or AWS). This is required to upload workspace profile image and workspace banner image. Without this, you'll not be able to test file upload features.
2. `HTTPS_CERT_API_HOST` and `HTTPS_CERT_API_KEY` are not required when testing on `localhost`.

#### D. Configure `auth` service's environment in docker-compose

1. Add `MAIL_USER` value with any of the test email account.
2. Add `MAIL_PASSWORD` value of the email account that you will use. If you're using `Google`, then you may need to create and use an app password and not your email account's original password.
   Google app passwords are used to allow applications or devices that don't support Google's two-step verification process to access your Google account. To generate an app password for your Google account, you can follow these steps:

    1. Go to your Google account settings page by visiting [https://myaccount.google.com/](https://myaccount.google.com/).
    2. Click on "Security" from the left-hand side menu.
    3. Scroll down to the "Signing in to Google" section and click on "App passwords".
    4. You may be prompted to enter your Google account password again to verify your identity.
    5. Next, select the app and device you want to generate a password for from the drop-down menus.
    6. Click on "Generate" to create the app password.
    7. Use the generated app password in place of your regular Google account password when prompted by the app or device.

    Note that you may need to repeat these steps to generate multiple app passwords for different apps or devices. You can also revoke app passwords that you no longer need.

3. Fill out `Google` and `Typeform` environments
4. Environment related to `stripe` are not required to test it out, unless you want to test pricing features.

#### E. Configure `integrations-typeform` and `integrations-googleform`

After configuring all the environments in the `docker-compose.yml` file, run the following command to start the services:

##  `docker login git.sireto.io:5050`
##  And sign in using your git.sireto.io login credentials
## `docker compose up --build --remove-orphans`

After running this command, you may need to login into stripe.

##### Full docker-compose file

```yaml
version: '3.7'
networks:
    db:
    backend:
    frontend:
volumes:
    mongo-data:
services:
    mongodb:
        image: mongo:latest
        networks:
            - db
        environment:
            MONGO_INITDB_ROOT_USERNAME: root
            MONGO_INITDB_ROOT_PASSWORD: root
        ports:
            - 27017:27017
        volumes:
            - mongo-data:/data/db
        restart: always

    mongo-seed:
        build:
            context: .
            dockerfile: Dockerfile.mongo-seed
        networks:
            - db
        depends_on:
            - mongodb

    # If you want to run webapp locally without using docker-compose,
    # you will also need to run nginx locally and not from docker-compose
    webapp:
        image: git.sireto.io:5050/bettercollected/webapp:nightly
        # image: bettercollected/webapp:nightly
        networks:
            - frontend
        environment:
            INTERNAL_DOCKER_API_ENDPOINT_HOST: http://backend:8000/api/v1
            API_ENDPOINT_HOST: http://localhost:8000/api/v1
            ADMIN_DOMAIN: localhost:3000
            CLIENT_DOMAIN: localhost:3001
            NEXT_PUBLIC_NODE_ENV: development
        ports:
            - '3000:3000'

    # You need to run nginx only if your webapp is running locally without using docker-compose
    # You may need to setup nginx locally with same configs provided inside `./nginx.conf`
    nginx:
        image: nginx
        networks:
            - frontend
        volumes:
            - ./nginx.conf:/etc/nginx/conf.d/nginx.conf:ro
        ports:
            - '80:80'
            - '3001:3001'
            - '3002:3002'

    backend:
        image: git.sireto.io:5050/bettercollected/backend:nightly
        # image: bettercollected/backend:nightly
        networks:
            - backend
            - db
            - frontend
        environment:
            AUTH_BASE_URL: http://auth:8000/api/v1
            AUTH_CALLBACK_URI: http://auth:8000/api/v1/auth/callback
        env_file:
            - .env
        ports:
            - '8000:8000'

    auth:
        image: git.sireto.io:5050/bettercollected/auth:nightly
        # image: bettercollected/auth:nightly
        networks:
            - backend
            - db
        environment:
            TYPEFORM_SCOPE: ${TYPEFORM_BASIC_SCOPE}
            TYPEFORM_REDIRECT_URI: ${TYPEFORM_BASIC_REDIRECT_URI}
            # Stripe
            STRIPE_SUCCESS_URL: ${STRIPE_REDIRECT_URL}
            STRIPE_CANCEL_URL: ${STRIPE_REDIRECT_URL}
            STRIPE_RETURN_URL: ${STRIPE_REDIRECT_URL}
        env_file:
            - .env
        ports:
            - '8001:8000'

    integrations-typeform:
        image: git.sireto.io:5050/bettercollected/integrations-typeform:nightly
        # image: bettercollected/integrations-typeform:nightly
        networks:
            - backend
            - db
        env_file:
            - .env
        ports:
            - '8002:8000'

    integrations-googleform:
        image: git.sireto.io:5050/bettercollected/integrations-googleform:nightly
        # image: bettercollected/integrations-googleform:nightly
        networks:
            - backend
            - db
        env_file:
            - .env
        ports:
            - '8003:8000'

```

Also put this environment variable in the same folder containing the docker-compose.yml file.
##### Environment Variables

```
    # Auth
- AUTH_AES_HEX_KEY='UAW6iquPs8Q2ZdKqjgIWcBZ-H8kPsGyFzedSGis7ZTA='
- AUTH_JWT_SECRET=qZ86c1g6Mm4J9cVSzx6zGeppUyqDpS31

# Mongo
- MONGO_URI=mongodb://root:root@mongodb:27017

# Stripe
- STRIPE_PRODUCT_ID=
- STRIPE_SECRET=
- STRIPE_WEBHOOK_SECRET=
- STRIPE_REDIRECT_URL=http://localhost:3000/refresh-token
- CLIENT_ADMIN_URL=http://localhost:3000

# Google
- GOOGLE_SCOPES='openid https://www.googleapis.com/auth/userinfo.profile https://www.googleapis.com/auth/userinfo.email https://www.googleapis.com/auth/drive.metadata.readonly https://www.googleapis.com/auth/forms.body.readonly https://www.googleapis.com/auth/forms.responses.readonly'
- GOOGLE_CLIENT_ID=132120488980-tnq1s7b7qfp876s67l77jmfukjonggpp.apps.googleusercontent.com
- GOOGLE_PROJECT_ID=bettercollected-sireto
- GOOGLE_CLIENT_SECRET=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
- GOOGLE_JAVASCRIPT_ORIGINS=http://localhost:3000,http://localhost:3001,http://localhost:3002
- GOOGLE_BASIC_AUTH_REDIRECT=http://localhost:8000/api/v1/auth/google/basic/callback
- GOOGLE_REDIRECT_URIS=http://localhost:8000/api/v1/auth/google/oauth/callback
- OAUTHLIB_INSECURE_TRANSPORT=1
- OAUTHLIB_RELAX_TOKEN_SCOPE=1

# Typeform
- TYPEFORM_BASIC_SCOPE=accounts:read
- TYPEFORM_SCOPE=offline+accounts:read+forms:read+responses:read
- TYPEFORM_CLIENT_ID=25cnSnYpD8x7RF85CAqfyQF1aHvubtxAh5mo4f4ruuFF
- TYPEFORM_CLIENT_SECRET=7ao4RFQnLVgzHDf5jN2pTgg8Q3QJzoM9wCa3sRMeRSHD
- TYPEFORM_BASIC_REDIRECT_URI=http://localhost:8000/api/v1/auth/typeform/basic/callback
- TYPEFORM_REDIRECT_URI=http://localhost:8000/api/v1/auth/typeform/oauth/callback

# Encryption
-MASTER_ENCRYPTION_KEYSET='ewogICAgICAgICAgImtleSI6IFt7CiAgICAgICAgICAgICAgImtleURhdGEiOiB7CiAgICAgICAgICAgICAgICAgICJrZXlNYXRlcmlhbFR5cGUiOgogICAgICAgICAgICAgICAgICAgICAgIlNZTU1FVFJJQyIsCiAgICAgICAgICAgICAgICAgICJ0eXBlVXJsIjoKICAgICAgICAgICAgICAgICAgICAgICJ0eXBlLmdvb2dsZWFwaXMuY29tL2dvb2dsZS5jcnlwdG8udGluay5BZXNHY21LZXkiLAogICAgICAgICAgICAgICAgICAidmFsdWUiOgogICAgICAgICAgICAgICAgICAgICAgIkdpQld5VWZHZ1lrM1JUUmhqL0xJVXpTdWRJV2x5akNmdENPeXBUcjBqQ05TTGc9PSIKICAgICAgICAgICAgICB9LAogICAgICAgICAgICAgICJrZXlJZCI6IDI5NDQwNjUwNCwKICAgICAgICAgICAgICAib3V0cHV0UHJlZml4VHlwZSI6ICJUSU5LIiwKICAgICAgICAgICAgICAic3RhdHVzIjogIkVOQUJMRUQiCiAgICAgICAgICB9XSwKICAgICAgICAgICJwcmltYXJ5S2V5SWQiOiAyOTQ0MDY1MDQKICAgICAgfQ=='

```

**Notes:**

-   If you want to run the web app locally without using docker-compose, you will also need to run nginx locally and not from docker-compose. You may need to set up nginx locally with the same configs provided inside ./nginx.conf.
-   If you want to run the Better Collected web app in production, you should modify the environment variables in the docker-compose.yml file to reflect your production settings.
-   The mongo-seed service builds an image using the Dockerfile.mongo-seed file in the current directory. This file should be present in the current directory, and should define how to seed the MongoDB instance with initial data.
-   The mongo-data volume is used to persist the data stored in the MongoDB instance between restarts.
-   The backend and auth services depend on the mongodb service, so they will not start until the mongodb service is up and running.
-   The webapp service depends on the backend service, and requires it to be running in order to function correctly.
-   The auth service is used for user authentication, and relies on several environment variables being set in order to function correctly. You will need to modify these environment variables to reflect your production settings.
-   The backend service is the API for the Better Collected web app, and also relies on several environment variables being set in order to function correctly. You will need to modify these environment variables to reflect your production settings.
-   The nginx service is used as a reverse proxy for the web app and is only needed if you want to run the web app locally without using docker-compose. If you are using docker-compose to run the web app, then nginx is automatically started and configured for you.

<hr/>

## Development Guide

For the development of the project, please refer to the [DEVELOPERS GUIDE](DEVELOPERS_GUIDE.md) documentation.
