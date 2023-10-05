<p align="center">
<img width="300" src="https://s3.eu-central-1.wasabisys.com/bettercollected/public/bettercollected_logo.png">
</p>

<p align="center" style="margin-top: 20px">
<b>Privacy-Friendly Form Builder For Conscious Companies</b>
</p>

## What is bettercollected? [🔗](https://bettercollected.com)

<hr/>
Better collected is a form builder platform that allows user to show that they care about their responders's data by allowing 
them to set purpose of the data collection which the responder gives consent to before submitting any form. In addition, it also allows the 
responder to view his/her submission and request for deletion of that response.

It provides a workspace that can be used to host all the forms in a single place.

More details about bettercollected can be found at [bettercollected](https://bettercollected.com)

## Try out cloud version

Our cloud version is at https://bettercollected.com

**or**

## Try it out yourself

This document explains the deployment guide for the users to see the deployed project locally.

## Sign in

### Email Sign In

Credentials for a mail client is required.
Update the following env variables in `.env.deployment`:

```dotenv
#Mail
MAIL_USER=
MAIL_PASSWORD=
MAIL_SMTP_SERVER=
MAIL_SMTP_PORT=
MAIL_SENDER=
```

**Using Gmail as Sender**

Create an app password in google. You can follow the steps here to create it: [Sign in with app passwords
](https://support.google.com/accounts/answer/185833)

```dotenv
MAIL_USERNAME=<GMAIL_USERNAME>
MAIL_PASSWORD=<APP_PASSWORD>
MAIL_FROM=<SENDER_ADDRESS>
MAIL_PORT=587
MAIL_SERVER=smtp.gmail.com
MAIL_FROM_NAME=<TITLE_FOR_MAIL>
```

## Running the services

#### In Linux/MacOs

Simply run the command:
```shell
./deploy
```

**Note**: For developer/contributor guide look into `docs/DEVELOPERS_GUIDE.md`

**Note**: For running the project with integrations, look into `docs/Running_Integrations.md`

