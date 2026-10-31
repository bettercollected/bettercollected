- The deployment compose file no longer runs `:nightly` images by default. The
  first-party images take `BC_IMAGE_TAG` (the shell's, else the root `.env`'s),
  and by default one pinned release (`v4.1.2`). `deploy.sh` with no
  `BC_IMAGE_TAG` set uses the release tag the checkout is on, so the images
  match the compose file and scripts of that release; a checkout between
  releases keeps the pinned default and says so. Set `BC_IMAGE_TAG=nightly`
  to follow `develop` on purpose.
