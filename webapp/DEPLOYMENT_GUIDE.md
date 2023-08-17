# DEPLOYMENT GUIDE

This document explains the deployment guide for the users to see the deployed project locally.

## IMPORTANT NOTE 

Users have to fill out some of the env variables themselves on `.env.deployment` before running the docker file.
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

## COMMANDs

 You can either run this project without `GoogleForm` and `Typeform` or you can run them optionally or run both. Below are the commands to run the docker container from this webapp repository.

 Since `runDocker` file is in current working directory so you can run following below commands based on your preferences.

 #### Run with both Googleform and Typeform

 ```
    ./runDocker both
 ```

  #### Run without both Googleform and Typeform

 ```
    ./runDocker none
 ```

#### Run with Googleform 

 ```
    ./runDocker googleform
 ```

  #### Run with Typeform

 ```
    ./runDocker typeform
 ```

 And finally you can stop running docker container using the following command:
 
 ```
   ./runDocker down
 ```