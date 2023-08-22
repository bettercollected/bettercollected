# DEVELOPERS GUIDE

This document explains the development guide to the new users participating in the development of the project.

### Directory Structure
1. `auth`:  the auth service
2. `backend`: the backend service
3. `common`: common module used across multiple projects
4. `integrations`: form builder integrations used in bettercollected 
   1. `google`
   2. `typeform`
5. `temporal`: Services related to temporal
   1. `worker` 


## Setup

#### Prerequisites
1. Python version `3.10` installed 
2. Poetry installed globally
3. Node version `16.18.0 or higher`

(**Note:** You can use nvm and pyenv to manage multiple versions of node and python respectively)

You can simply run the following command 
```
./install.sh 
```

### Configure Nginx locally to map the path for `ADMIN_HOST`, `CLIENT_HOST`, and `CUSTOM_DOMAIN` to load all of them at once.

This can be done in two ways:

#### 1. Using Docker compose

If you do not have nginx installed in your system then you can simply use the `nginx` service in `docker-compose.local.yml`.


#### 2. Using locally installed Nginx

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

### Default and Custom Domain Configuration

1. To go `CLIENT_HOST` as the default domain, navigate to `localhost:3001/{workspace_handle}`.
2. To go to the Custom Domain, follow the process below
    - Update a workspaces' custom domain e.g. `localhost:3002` to set up localhost:3002 as a custom domain (This also needs to be saved in database inside `allowed_origins` in a new document)
    - Run the app in `localhost:3002` and you can access your custom domain at `localhost:3002`


### Run database using docker

Since All repositories depend on mongo database, so you will need to run mongo before running `Backend` and `Auth` repositories. To run the database
use following command to run the docker container from this webapp repository.

```
    docker compose -f "docker-compose.local.yml" up --build -d
```


This will create and seed required databases to run all backend.

### Alternative for database

If you want to use an existing deployment of mongodb, make sure that you seed the data that has been seeded with `seed-data.js` in `bettercollected_backend` database manually as given below.

1. Use CLI or `MongoDB Compass` to connect to MongoDB . `MongoDB Compass` is preferred [Installation Link](https://www.mongodb.com/try/download/compass).
2. Inside `bettercollected_backend` database, go to `allowed_origins` collection, if not present, you can create it manually.
3. Add individual document for `localhost:3000`, `localhost:3001`, and `localhost:3002` with a field like:
    ```
     "origin":"http://localhost:3000"  # Replace 3000 with 3001 and 3002
    ```
4. Also go to 'forms_plugin_configs' collection, if not present create it manually.
5And then add individual document for `google` and `typeform` with a field like:
    ```
        "enabled":"true"
        "provider_name":"typeform"      # Replace typeform with `google`
        "provider_url":"http://localhost:8002/api/v1"       # Replace `8002` with `8003`
        "auth_callback_url":"http://localhost:8002/api/v1/typeform/oauth/callback"      # Replace typeform with `google` and replace `8002` with `8003`
        "type":"oauth2"
    ```


## Running all services locally

You can simply run all the required services by using the following command
```shell
./run.sh
```

Or, you can individually run each service by navigating to it and running the same above command.

### Walk through `README.md`

1.  Use python version `3.10` , if you don't have then install using pyenv with command `pyenv install version_number` and set it global with `pyenv global version_number`.
2.  Walk through `README.md` of all the individual services.
3.  Also, inside each repository set up for "common" submodule with command if not already up to date:
    `git submodule update --init --recursive --remote`
    And then navigate to common submodule `cd common` and checkout master branch `git checkout master && git pull` and `cd ..`.
