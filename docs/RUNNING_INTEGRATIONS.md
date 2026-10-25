## Options for running Integrations

### Google

Users have to fill out some of the env variables themselves in `.env.deployment` before running the docker file (`deploy.sh` creates it from the template `.env.deployment.example` on the first run; to create it yourself: `(umask 077; cp .env.deployment.example .env.deployment)`).
For using `Google forms` you need to set up certain environment variables, for that create a project
in `Google Cloud Platform` and fill the following environment variables.

```dotenv
GOOGLE_CLIENT_ID=
GOOGLE_PROJECT_ID=
GOOGLE_CLIENT_SECRET=
```

#### The Google Forms import switch (`GOOGLE_FORMS_IMPORT`)

Read by the backend and the Google Forms service (set it to the same value for both):

| Value | Effect |
|---|---|
| `on` (default) | Imports, re-syncs and connecting a Google account work. |
| `readonly` | Forms and responses imported earlier stay readable and manageable here. Nothing is processed with Google any more: no new import, no re-sync (importing an imported form again), no connection or token refresh, no listing of Google forms. These requests answer 403 with `{"code": "google_forms_readonly"}`. The Google Sheets action and deleting stored Google credentials (account deletion, which also revokes the grant at Google: one call that ends access) keep working. bettercollected.com runs in this mode. |
| `off` | The Google Forms endpoints answer 410 with `{"code": "google_forms_off"}` and the backend never calls the Google Forms service. Google is not listed in `GET /providers`. The Google Sheets action stops too while it still goes through that service, and account deletion erases the Google credentials stored there through the database function `google.purge_user_credentials` (a queued `purge_provider_credentials` job; needs `JOBS_BACKEND__purge_provider_credentials=postgres` and the Google data on Postgres only); a Mongo or dual Google store needs the service running for that. |

`GET /providers` reports the mode for Google (`importMode`: `on` or `readonly`), so the webapp can say why
imports are not offered. An unknown value stops the backend at startup; the Google Forms service treats
it as `off`.

##### Stored Google credentials on account deletion

The backend asks the Google Forms service to erase them (`POST /google/oauth/credentials/erase`; the user id
and email travel in the JSON body, so URLs and access logs carry no email). This happens for the Google
provider whether it is enabled or disabled. When the call fails, or in `off`, it queues a
`purge_provider_credentials` job (procrastinate only, so set `JOBS_BACKEND__purge_provider_credentials=postgres`).
The job retries hourly for two days. A purge that is still pending a day after it was queued, or that failed,
shows in the admin portal's integrity monitor (`CREDENTIAL_PURGE` / `overdue`).

If the job can't be queued, the account deletion fails after the erasure and is retried. Where it shows depends
on `JOBS_BACKEND__delete_user`:

- `postgres`: the failing deletion job is counted by the same integrity monitor.
- `temporal` (the default): Temporal retries the workflow's activity. The failure shows in the Temporal UI and
  as an error log line ("could not be queued"), not in the integrity monitor.

Known limits of the database purge in `off` (`google.purge_user_credentials`):

- It succeeds when it deletes 0 rows. It deletes only rows that match both the user id and the email, so rows
  stored without a `user_id` (credentials connected by older versions) never match it. Erase those by
  email by hand, or run the service in `on`/`readonly` for the purge, where the service matches either.
- It runs only when the backend's flags for the `google` group say Postgres only (`DB_WRITE_MODE__GOOGLE=postgres`
  or `DB_WRITE_MODE=postgres`). The Google Forms service itself stores its data in Postgres only since 4.1 and
  refuses to start while its own `DB_READ_SOURCE`/`DB_WRITE_MODE` (or their `__google` overrides) name another
  store.

#### Steps to create a client in Google:

##### Important Note: Steps 5, 6 and 12 are needed only if you want to run Google form integration.

1. Go to the [Google Cloud Console](https://console.cloud.google.com/) and sign in to your account.
2. Create a new project by clicking on the dropdown menu at the top of the screen and selecting "New Project".
3. Enter a name for your project and click on the "Create" button.
4. Once your project is created, select it from the dropdown menu at the top of the screen.
5. In the left sidebar, click on the "APIs & Services" option.
6. Click on the "Enabled APIs & Services", and enable "Google Forms API" and "Google Drive API".
7. Click on the "Credentials" tab.
8. Click on the "Create Credentials" button and select "OAuth client ID" from the dropdown menu.
9. Select "Web App" as the application type and enter a name for your OAuth client ID.
10. Add Redirect URIs: `http://localhost:8000/api/v1/auth/google/basic/callback`  Also, add three JavaScript
    origins: `http://localhost:3000`, `http://localhost:3001`, and `http://localhost:3002`.

    **Note**: Add a redirect URI if you want to use import functionality
    i.e. `http://localhost:8000/api/v1/auth/google/oauth/callback`

11. Click on the "Create" button.
12. Click on the "OAuth consent screen". From here, you can add new test users and add different scopes. The required
    scopes for our application to run
    are: `auth/userinfo.email`, `auth/userinfo.profile`, `openid`, `auth/forms.body.readonly`, `auth/forms.responses.readonly`,
    and `auth/drive.metadata.readonly`.
13. In the "OAuth client ID" page, you can find your client ID and client secret.
14. Click on the "Download" button to download your client secret as a JSON file.
    Once you have generated your client secret, you can use it in your application to authenticate with Google APIs.

### Typeform

The Typeform integration was removed in 4.1. Forms and responses imported from Typeform before
that stay readable as ordinary forms. `./deploy.sh typeform` and `./deploy.sh both` are refused
(exit code 2, nothing changed): run `./deploy.sh` instead of `typeform`, and
`./deploy.sh googleform` instead of `both`. Any `TYPEFORM_*` value left in an env file or the
settings store is ignored.

## Running the project

#### Run without the Google Forms integration

 ```
    ./deploy 
 ```

#### Run with Googleform

 ```
    ./deploy googleform
 ```

#### And finally you can stop all running services using the following command:

 ```
   ./deploy down
 ```

**Note**: If you have already run the project without any integrations and want to run it again with integrations enabled. You might need to change the `enabled` field of the integration 
in `forms_plugin_configs` document in `bettercollected_backend` database. 

**Note**: If you want to enable/disable for the integrations by changing the `enabled` field in
mongoDB `forms_plugin_configs` document

#### Important note: `deploy.sh` generates the stack's own `AUTH_JWT_SECRET`, `AUTH_AES_HEX_KEY` and `MASTER_ENCRYPTION_KEYSET` into the root `.env`; keep that file, and change any other credentials in `.env.deployment` before deploying to production
