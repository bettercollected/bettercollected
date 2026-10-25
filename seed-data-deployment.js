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

// Nothing else: the reference data (allowed origins, the Google Forms provider) is
// served from Postgres since 4.1 and seeded there by deploy.sh
// (python -m backend.seed_refdata). Collections an earlier release seeded here are
// left as they are, for the import into Postgres.
