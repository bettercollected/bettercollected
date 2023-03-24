# Better Collected

Source code for Better Collected, with Next.js version `12.3.1`.

## Runtime Environment Variables

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


### Project Setup and Scripts

1. If you are using `nvm`, install node version `16 LTS` and run `nvm alias default 16` to set the default node environment or run `nvm use` to use the version from [.nvmrc](.nvmrc)](.nvmrc). Else, use node version `16`.
2. Run `yarn install` in the terminal to set up the project and husky configuration.
3. Run `yarn dev` to start the project locally.
4. Run `yarn build` and `yarn start` to start production build.
5. Run `yarn clean` to clear cache, node_modules, and build folders.
6. `(Optional) Should be done automatically during the package installation process (i.e. npm install)` Run `yarn prepare` to install and initialize husky for commit hooks

### Development

For the development of the project, please refer to the [DEVELOPERS GUIDE](DEVELOPERS_GUIDE.md) documentation.

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


### Add the localhost inside the database

1. Go to `backend` datasbe in the MongoDB, if not present, run the `bettercollected-backend` repo, the database should be created if all the configuration is correct.
2. Inside `backend` database, go to `allowed_origins` collection, if not present, you can create it manually.
3. Add individual document for `localhost:3000`, `localhost:3001`, and `localhost:3002` with a field like:
   ```
    "origin":"http://localhost:3000"  # Replace 3000 with 3001 and 3002
   ```

### Default and Custom Domain Configuration

1. To go `CLIENT_HOST` as the default domain, navigate to `localhost:3001/{workspace_handle}`.
2. To go to the Custom Domain, follow the process below
    - Update a workspace's custom domain e.g. `localhost:3002` to set up localhost:3002 as a custom domain (This also needs to be saved in database inside `allowed_origins` in a new document)
    - Run the app in `localhost:3002` and you can access your custom domain at `localhost:3002`
