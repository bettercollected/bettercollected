# DEPLOYMENT GUIDE

This document explains the deployment guide for the users to see the deployed project locally.

## Sin in Options

### Google
Users have to fill out some of the env variables themselves on `.env.deployment` before running the docker file.
For using `Google forms` you need to set up certain environment variables, for that create a project in `Google Cloud Platform` and fill the following environment variables.

```dotenv
   GOOGLE_CLIENT_ID=
   GOOGLE_PROJECT_ID=
   GOOGLE_CLIENT_SECRET=
```
 
#### Steps to create a client in Google:

##### Important Note: Steps 5, 6 and 11 are needed only if you want to run Google form integration.

1. Go to the [Google Cloud Console](https://console.cloud.google.com/) and sign in to your account.
2. Create a new project by clicking on the dropdown menu at the top of the screen and selecting "New Project".
3. Enter a name for your project and click on the "Create" button.
4. Once your project is created, select it from the dropdown menu at the top of the screen.
5. In the left sidebar, click on the "APIs & Services" option.
6. Click on the "Enabled APIs & Services", and enable "Google Forms API" and "Google Drive API".
7. Click on the "Credentials" tab.
8. Click on the "Create Credentials" button and select "OAuth client ID" from the dropdown menu.
9. Select "Web App" as the application type and enter a name for your OAuth client ID.
10. Add Redirect URIs: `http://localhost:8000/api/v1/auth/google/basic/callback`  Also, add three JavaScript origins: `http://localhost:3000`, `http://localhost:3001`, and `http://localhost:3002`.

    **Note**: Add a redirect URI if you want to use import functionality i.e. `http://localhost:8000/api/v1/auth/google/oauth/callback`

11. Click on the "Create" button.
12. Click on the "OAuth consent screen". From here, you can add new test users and add different scopes. The required scopes for our application to run are: `auth/userinfo.email`, `auth/userinfo.profile`, `openid`, `auth/forms.body.readonly`, `auth/forms.responses.readonly`, and `auth/drive.metadata.readonly`.
13. In the "OAuth client ID" page, you can find your client ID and client secret.
14. Click on the "Download" button to download your client secret as a JSON file.
    Once you have generated your client secret, you can use it in your application to authenticate with Google APIs.

### Typeform

Similarly for using `Typeform` you need to set up certain environment variables and for that create a `Typeform` account and add your app in `Developer apps` to get the value for following environment variables.

```dotenv
   TYPEFORM_CLIENT_ID=
   TYPEFORM_CLIENT_SECRET=
```

#### Steps to create a client in Typeform:

1. Go to the [Admin Typeform's Developer Apps](https://admin.typeform.com/).
2. Go to Developer apps from the dashboard and "Register a new app".
3. Fill up the details and set the "Redirect URIs": `http://localhost:8000/api/v1/auth/typeform/basic/callback` and `https://localhost:8000/api/v1/auth/typeform/oauth/callback`.
4. Once you register the new app, you'll see a `secret`. You need to save this secret some place safe as you'll not see this again.
5. You can see the `client_id` whenever you want to.


### Email Sign In

There is an option to log in by using email. So, credentials for a mail client is required to use this feature.
Update the following env variable in `.env.deployment`:

```dotenv
    #Mail
    MAIL_USER=
    MAIL_PASSWORD=
    MAIL_SMTP_SERVER=
    MAIL_SMTP_PORT=
    MAIL_SENDER=
```


## COMMANDs

 You can either run this project without `GoogleForm` and `Typeform` or you can run them optionally or run both. Below are the commands to run the docker container from this webapp repository.

 Since `deploy` file is in current working directory so you can run following below commands based on your preferences.

 #### Run with both Googleform and Typeform Integrations

 ```
    ./deploy both
 ```

  #### Run without both Googleform and Typeform Integrations

 ```
    ./deploy 
 ```

#### Run with Googleform 

 ```
    ./deploy googleform
 ```

  #### Run with Typeform

 ```
    ./deploy typeform
 ```

 #### And finally you can stop all running services using the following command:
 
 ```
   ./deploy down
 ```

**Note**: For developer/contributor guide look into `DEVELOPERS_GUIDE.md`

