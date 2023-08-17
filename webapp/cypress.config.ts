import { defineConfig } from 'cypress';

export default defineConfig({
    component: {
        devServer: {
            framework: 'next',
            bundler: 'webpack'
        }
    },

    e2e: {
        setupNodeEvents(on, config) {
            // implement node event listeners here
        }
    },
    env: {
        baseUrl: 'https://admin.bettercollected.com/login'
    }
});
