#!/bin/bash

API_ENDPOINT_HOST=https://bettercollected.io/api/v1
DASHBOARD_DOMAIN=admin.bettercollected.io
FORM_DOMAIN=forms.bettercollected.io
NEXT_PUBLIC_UNSPLASH_ACCESS_KEY=cjNqTgaSqmYzOZETsWrivtF1ayn4PGzy_NPWZDkZG_A


docker build --build-arg NEXT_PUBIC_API_ENDPOINT_HOST=${API_ENDPOINT_HOST} --build-arg NEXT_PUBLIC_UNSPLASH_ACCESS_KEY=${NEXT_PUBLIC_UNSPLASH_ACCESS_KEY} --build-arg NEXT_PUBLIC_DASHBOARD_DOMAIN=${DASHBOARD_DOMAIN} --build-arg NEXT_PUBLIC_FORM_DOMAIN=${FORM_DOMAIN} -f webapp/Dockerfile -t bettercollected/webapp:nightly .
# docker push bettercollected/webapp:nightly
