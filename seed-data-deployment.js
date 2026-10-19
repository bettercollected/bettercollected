// Run by mongosh --nodb (Dockerfile.deployment.mongo-seed): the root password comes
// from the environment, never from a command line, where other users of the host
// could read it in the process list.
const rootPassword = process.env.MONGO_ROOT_PASSWORD || 'root';
const connection = new Mongo('mongodb://mongodb:27017');
connection.getDB('admin').auth('root', rootPassword);
db = connection.getDB('bettercollected_backend');

// Earlier releases created a `seeduser` (password "seeduser") with readWrite on
// this database on every deploy. Nothing uses it: remove it from volumes that
// still have it, and never create it again.
try {
    db.dropUser('seeduser');
} catch (error) {
    // not there: nothing to remove
}

// Check if the collection exists
const collectionNames = db.getCollectionNames();

const googleEnabled = process.env.GOOGLE_ENABLED === "true"
const typeformEnabled = process.env.TYPEFORM_ENABLED === "true"

console.log("Google", googleEnabled)
console.log("Typeform", typeformEnabled)


if (collectionNames.indexOf('allowed_origins') !== -1) {
} else {
    db.createCollection('allowed_origins');
    db.allowed_origins.insertMany([{origin: 'http://localhost:3000'}, {origin: 'http://localhost:3001'}, {origin: 'http://localhost:3002'}]);
}

if (collectionNames.indexOf('forms_plugin_configs') !== -1) {
} else {
    // When running through docker compose, these data are automatically added if its empty
    // If you are running your backend, auth, and other integrations locally, you will need to
    // replace `auth_callback_url` with `localhost:<PORT>` instead of `integrations-<PROVIDER>`
    db.createCollection('forms_plugin_configs');
    db.forms_plugin_configs.insertMany([
        {
            enabled: typeformEnabled,
            provider_name: 'typeform',
            provider_url: 'http://integrations-typeform:8000/api/v1',
            auth_callback_url: 'http://integrations-typeform:8000/api/v1/typeform/oauth/callback',
            type: 'oauth2'
        },
        {
            enabled: googleEnabled,
            provider_name: 'google',
            provider_url: 'http://integrations-googleform:8000/api/v1',
            auth_callback_url: 'http://integrations-googleform:8000/api/v1/google/oauth/callback',
            type: 'oauth2'
        }
    ]);
}
