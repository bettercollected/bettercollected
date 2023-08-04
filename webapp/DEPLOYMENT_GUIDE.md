# DEPLOYMENT GUIDE

This document explains the deployment guide for the users to see the deployed project locally.

## IMPORTANT NOTE 

Users have to fill out some of the env variables themselves before running the docker file.
For using `Google forms` you need to set up certain environment variables, for that create a project in `Google Cloud Platform` and fill the following environment variables.

```
   GOOGLE_SCOPES=
   GOOGLE_CLIENT_ID=
   GOOGLE_PROJECT_ID=
   GOOGLE_CLIENT_SECRET=
```

Similarly for using `Typeform` you need to set up certain environment variables and for that create a `Typeform` account and add your app in `Developer apps` to get the value for following environment variables.

```
   TYPEFORM_BASIC_SCOPE=
   TYPEFORM_SCOPE=
   TYPEFORM_CLIENT_ID=
   TYPEFORM_CLIENT_SECRET=
```

## COMMAND

 Finally use the below command to run your docker container from this webapp repository.

 ```
    docker compose -f "docker-compose.deployment.yml" up -d
 ```