db.dropAllUsers();

db.createUser({
    user: 'seeduser',
    pwd: 'seeduser',
    roles: [{ role: 'readWrite', db: 'bettercollected_backend' }]
});

// Check if the collection exists
const collectionNames = db.getCollectionNames();

if (collectionNames.indexOf('allowed_origins') !== -1) {
} else {
    db.createCollection('allowed_origins');
    db.allowed_origins.insertMany([{ origin: 'http://localhost:3000' }, { origin: 'http://localhost:3001' }, { origin: 'http://localhost:3002' }]);
}

if (collectionNames.indexOf('forms_plugin_configs') !== -1) {
} else {
    // When running through docker compose, these data are automatically added if its empty
    // If you are running your backend, auth, and other integrations locally, you will need to
    // replace `auth_callback_url` with `localhost:<PORT>` instead of `integrations-<PROVIDER>`
    db.createCollection('forms_plugin_configs');
    db.forms_plugin_configs.insertMany([
        {
            enabled: true,
            provider_name: 'typeform',
            provider_url: 'http://localhost:8002/api/v1',
            auth_callback_url: 'http://localhost:8002/api/v1/typeform/oauth/callback',
            type: 'oauth2'
        },
        {
            enabled: true,
            provider_name: 'google',
            provider_url: 'http://localhost:8003/api/v1',
            auth_callback_url: 'http://localhost:8003/api/v1/google/oauth/callback',
            type: 'oauth2'
        }
    ]);
}
