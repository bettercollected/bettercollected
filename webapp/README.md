# Better Collected

Source code for Better Collected, with Next.js version `12.3.1`.

## Runtime Environment Variables

Please refer to the [.env.example](.env.example) file for updated environment variables

-   GA_MEASUREMENT_ID
-   WAITLIST_FORM_URL
-   CONTACT_US_URL
-   INDIVIDUAL_FORM
-   BUSINESS_FORM
-   ENTERPRISE_FORM
-   NEXT_PUBLIC_NODE_ENV

### Project Setup and Scripts

1. If you are using `nvm`, install node version `16 LTS` and run `nvm alias default 16` to set the default node environment or run `nvm use` to use the version from [.nvmrc](.nvmrc)](.nvmrc). Else, use node version `16`.
2. Run `yarn install` in the terminal to set up the project and husky configuration.
3. Run `yarn dev` to start the project locally.
4. Run `yarn build` and `yarn start` to start production build.
5. Run `yarn clean` to clear cache, node_modules, and build folders.
6. `(Optional) Should be done automatically during the package installation process (i.e. npm install)` Run `yarn prepare` to install and initialize husky for commit hooks

### Development

For the development of the project, please refer to the [DEVELOPERS GUIDE](DEVELOPERS_GUIDE.md) documentation.

### Default and Custom Domain Configuration

1. Set `CLIENT_HOST` as the default domain.
2. To Set up Custom Domain Follow the process below
    - Update a worksapce's custom domain e.g. `localhost:3001` to set up localhost:3001 as a custom domain
    - run the app in `localhost:3001` and you can access your custom domain at `localhost:3001`
