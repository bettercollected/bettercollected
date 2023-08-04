# DEPLOYMENT GUIDE

This document explains the deployment guide for the users to see the deployed project locally.

## IMPORTANT NOTE 

Users have to fill out some of the env variables themselves before running the docker file.
For google related environment variables, create a project in `Google Cloud Platform` and fill the empty environment variables.
Similarly for typeform related environment variables create a `Typeform` account and add your app in `Developer apps` to get the value for typeform related environment variables.

## COMMAND

 Finally use the below command to run your docker container.

 ```
    docker compose -f "docker-compose.deployment.yml" up -d
 ```