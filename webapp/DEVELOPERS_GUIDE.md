# DEVELOPERS GUIDE

This document explains the development guide to the new users participating in the development of the project.

## IMPORTANT NOTE

Use terminal to perform `git commit` action to see proper error messages. Integrated Commit feature in IDE's like WebStorm
might not show detailed errors if we encounter any `(It's much easier to view errors in terminal)`. The reason is that we have
set up `husky` for running some scripts to check the `Code Format, ESLinting, TSConfiguration Standards` before committing, and if some scripts generate error, it is easier to debug.

### Configurations

1. Setup prettier as a code formatter during the development of this project.
2. TypeScript's configuration are set in [tsconfig.json](tsconfig.json). Update as per the requirements.
3. [ESLint](.eslintrc.json) and [Prettier](prettier.config.js) are used to provide better development experience and consistence code.
4. Husky configurations are set in [Husky](.husky/pre-commit).
5. Global media assets are set on [public](public) folder at the root level and [assets](src/assets) folder inside `src`.
6. Copy [.env.example](.env.example) file, rename it to `.env`, and add appropriate environment variables there. `[NOTE: If any new environment variable is added to the project, do not forget to add it in .env.example file as well]`

### Runtime Environment Variables

Please refer to the [.env.example](.env.example) file for updated environment variables

-   BASE_DEPLOY_PATH
-   GA_MEASUREMENT_ID
-   NEXT_PUBLIC_NODE_ENV
-   GOOGLE_IMAGE_DOMAINS
-   API_ENDPOINT_HOST
-   CLIENT_HOST
-   ENABLE_GOOGLE
-   ENABLE_TYPEFORM
-   ENABLE_BRAND_COLORS

### Directory Structure

1. All the `.ts, .js, .tsx, .jsx` code are inside the [src](src) directory.
2. [assets](src/assets) directory includes all the static css, images, and svg.
3. [components](src/components) directory includes all the reusable components, stories, and tests (i.e. common and other components).
    1. [components/icons](src/components/icons) directory includes all the custom svg icons.
    2. [components/ui](src/components/ui) directory includes all the custom shared UI.
    3. [components/drawer-views](src/components/drawer-views) includes all the logic for opening up drawer.
    4. [components/settings](src/components/settings) includes all the settings options for the whole app.
    5. [components/modal-views](src/components/modal-views) includes all the logic for opening modal views.
    6. [components/search-view](src/components/search-view) includes all the logic for opening search view.
4. [configs](src/configs) directory includes all the configurations used in the app.
5. [constants](src/constants) directory includes all the constants related to assets, global, shades, textStyles, formProps. Feel free to add other constants to this directory.
6. [containers](src/containers) directory includes all the main view, stories, and tests for each specific pages.
7. [layouts](src/layouts) directory includes common shared design in all the pages.
8. [lib](src/lib) directory includes all custom `hooks` and `wallet` connection required for the project.
    1. [lib/hooks](src/lib/hooks) directory includes all custom hooks.
    2. [lib/framer-motion](src/lib/framer-motion) directory includes all animations.
    3. [lib/wallet](src/lib/wallet) directory includes wallet connection and kuber transactions.
9. [models](src/models) directory includes all dtos, enums, and types.
10. [pages](src/pages) directory includes actual pages.
11. [store](src/store) directory includes configurations for redux store and other app specific reducers, actions, and types.
12. [types](src/types) directory includes common types.
13. [utils](src/utils) directory includes all the essentials, and custom utilities files.

### Project Setup and Scripts

1. If you are using `nvm`, install node version `16 LTS` and run `nvm alias default 16` to set the default node environment or run `nvm use` to use the version from [.nvmrc](.nvmrc)](.nvmrc). Else, use node version `16`.
2. Run `yarn install` in the terminal to set up the project and husky configuration.
3. Run `yarn dev` to start the project locally.
4. Run `yarn build` and `yarn start` to start production build.
5. Run `yarn clean` to clear cache, node_modules, and build folders.
6. `(Optional) Should be done automatically during the package installation process (i.e. npm install)` Run `yarn prepare` to install and initialize husky for commit hooks

### Configure Nginx locally to map the path for ADMIN_HOST, CLIENT_HOST, and CUSTOM DOMAIN to load all of them at once.

1. Install `nginx` with `sudo apt install nginx`.
2. Check if the `nginx` service is running or not with `systemctl status nginx`. If it's not running, start the service by running `systemctl start nginx`.
3. Next step is to update the config files for nginx. Run `touch /etc/nginx/conf.d/default.conf` and `nano /etc/nginx/conf.d/default.conf` (The config names can be anything). After that paste the following in that config and save it.

    ```
    server {
        listen 3001;

        location / {
            proxy_pass http://localhost:3000;
            proxy_set_header Host $host:$server_port;
        }
    }
    ```

    <br/>
    In the same way, create another config file with a name `custom-domain-bettercollected.conf` and paste the following in this config and save it.

    ```
    server {
        listen 3002;

        location / {
            proxy_pass http://localhost:3000;
            proxy_set_header Host $host:$server_port;
        }
    }
    ```

4. After adding the config, restart the nginx with `systemctl restart nginx`.
5. After this, you'll be able to see `ADMIN_HOST` in `localhost:3000`, `CLIENT_HOST` in `localhost:3001/{workspace_handle}`, and `CUSTOM_DOMAIN` in `localhost:3002`.

### Walk through `README.md`

1.  Walk thorugh `README.md` of this repository `bettercollected` and other dependent repositories `bettercollected-auth`,`bettercollected-backend`,`bettercollected-integrations-google-forms`,`bettercollected-integrations-typeform`.
2.  Use python version `3.10` , if you dont have then install using pyenv with command `pyenv install version_number` and set it global with `pyenv global version_number`.
3.  Also inside each repository set up for "common" submodule with command:
    `git submodule update --init --recursive --remote`
    And then navigate to common submodule `cd common` and checkout master branch `git checkout master && git pull` and `cd ..`.

### Run database using docker

Since `Backend` and `Auth` repositories depends on mongo database so you will need to run mongo before running `Backend` and `Auth` repositories. To run the database
use following command to run the docker container 

```
    docker compose -f "docker-compose.local.yml" up -d
```

<!-- 1. Go to `backend` database in the MongoDB, if not present, run the `bettercollected-backend` repo, the database should be created if all the configuration is correct.
2. If not then you can run `mongoDB` locally by creating `docker compose` file which looks like:
    ```
        version: "3.7"
        networks:
        default:
            name: mongodb
            attachable: true
        services:
        mongodb_container:
            image: mongo:latest
            environment:
            MONGO_INITDB_ROOT_USERNAME: <mongoDB_user>
            MONGO_INITDB_ROOT_PASSWORD: <mongoDB_password>
            ports:
            - 27017:27017
            volumes:
            - mongodb_data_container:/data/db
            restart: always
        volumes:
        mongodb_data_container:
    ```
    and finally use command `docker compose up`.
3. Use CLI or `MongoDB Compass` to connect to MongoDB . `MongoDB Compass` is preferred [Installation Link](https://www.mongodb.com/try/download/compass).
4. Inside `backend` database, go to `allowed_origins` collection, if not present, you can create it manually.
5. Add individual document for `localhost:3000`, `localhost:3001`, and `localhost:3002` with a field like:
    ```
     "origin":"http://localhost:3000"  # Replace 3000 with 3001 and 3002
    ```
6. Also go to 'forms_plugin_configs' collection, if not present create it manually.
7. And then add individual document for `google` and `typeform` with a field like:
    ```
        "enabled":"true"
        "provider_name":"typeform"      # Replace typeform with `google`
        "provider_url":"http://localhost:8002/api/v1"       # Replace `8002` with `8003`
        "auth_callback_url":"http://localhost:8002/api/v1/typeform/oauth/callback"      # Replace typeform with `google` and replace `8002` with `8003`
        "type":"oauth2"
    ``` -->

### Default and Custom Domain Configuration

1. To go `CLIENT_HOST` as the default domain, navigate to `localhost:3001/{workspace_handle}`.
2. To go to the Custom Domain, follow the process below
    - Update a workspace's custom domain e.g. `localhost:3002` to set up localhost:3002 as a custom domain (This also needs to be saved in database inside `allowed_origins` in a new document)
    - Run the app in `localhost:3002` and you can access your custom domain at `localhost:3002`
