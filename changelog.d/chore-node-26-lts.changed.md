- The web app image now runs on Node 26 (the current LTS line) instead of Node 22, and
  the base image is pinned by digest. It is built in CI like before; no change to the
  stack or its environment is needed. Building the web app from source needs Node 26
  (22.12 or later works), and Yarn 1 is installed with `npm i -g yarn`, as Node 25 and
  later no longer ship Corepack.
