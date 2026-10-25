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
- It needs the backend's Postgres connection, and no storage flag: the Google Forms service stores its data in
  Postgres only since 4.1, and refuses to start while its own `DB_READ_SOURCE`/`DB_WRITE_MODE` (or their
  `__google` overrides) name another store.

#### The Google Sheets action (`GOOGLE_SHEETS_OAUTH`)

The "Google Sheets" form action appends each submission to a spreadsheet it creates in the form owner's
Google Drive. Who runs its OAuth flow (connecting the account and creating the spreadsheet) is chosen by
`GOOGLE_SHEETS_OAUTH`, read by the backend:

| Value | Effect |
|---|---|
| `google_service` (default) | As before: the Google Forms service builds the authorization URL with its own client and `GOOGLE_SHEET_SCOPE` (`spreadsheets` + `drive`), exchanges the code and creates the spreadsheet. It stops with `GOOGLE_FORMS_IMPORT=off`. |
| `backend` | The backend runs the flow itself with the Google sign-in client (`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_TOKEN_URI`, as used by the auth service) and asks for one scope only: `https://www.googleapis.com/auth/drive.file` (the files this app creates). The Google Forms service is not called, so `GOOGLE_FORMS_IMPORT` does not affect the action. Without a client id and secret the connect request answers 503. |

The redirect address is the web app's callback page in both modes, `GOOGLE_SHEET_REDIRECT_URL`
(for example `https://app.example.com/integrations/google/callback`); in `backend` mode the backend reads it.
The stored credential has the same format either way, so the actions executor needs no change. In
`backend` mode, actions connected before with the broad grant must be reconnected (below).

Before setting `GOOGLE_SHEETS_OAUTH=backend`:

1. In the Google Cloud console, open the OAuth client used for Google sign-in (the one `GOOGLE_CLIENT_ID`
   names) and add the value of `GOOGLE_SHEET_REDIRECT_URL` to its authorized redirect URIs.
2. On the project's OAuth consent screen (Data access), add the scope `.../auth/drive.file`. It is a
   non-sensitive scope, so no extra verification is needed for it.
3. Make sure the Google Sheets API is enabled for the project.
4. Set `GOOGLE_SHEETS_OAUTH=backend` for the backend (and `GOOGLE_SHEET_REDIRECT_URL` if the backend does not
   have it yet) and restart it.

Going back is setting `google_service` again. Actions connected in `backend` mode keep running in either mode.

##### Grants from before `drive.file`: reconnect on next use

A stored Sheets credential whose `scopes` is anything other than exactly
`https://www.googleapis.com/auth/drive.file` (the Google Forms service's flow granted `spreadsheets` and
full `drive` access) is never used again in `backend` mode. On its next use (a submission that would run
the action, or opening it in the builder, `GET /workspaces/{workspace_id}/forms/{form_id}/actions/{action_id}/reconsent`)
the backend:

- does not run the action for that submission and counts the skipped run; the submission itself is stored
  as usual and other actions run;
- marks the action `needs_reconsent` (parameters on the form's action: `needs_reconsent`,
  `reconsent_skipped_runs`, `reconsent_mailed_at`; no migration);
- mails the workspace's billing owner once per action ("Reconnect Google Sheets", in the form's language,
  English or Dutch) through the auth service, with a link to the form's integrations. When the auth service
  cannot be reached, the next use tries again.

Reconnecting (connect and save the action again) stores a `drive.file` credential and new parameters,
which clears the marks. In `google_service` mode nothing is held back: reconnecting there grants the broad
scopes again. Logs carry form, action and workspace ids and counts only.

Before switching, count the actions concerned (read-only, counts only):

```bash
python -m backend.sheets_legacy
```

It prints `sheets_actions_with_credential`, `legacy` (including `unreadable` credentials), `drive_file`,
`needs_reconsent_marked`, `owners_mailed`, `skipped_runs` and `forms`.

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
