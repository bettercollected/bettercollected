# bettercollected-backend-server
[![CI](/actions/workflows/main.yml/badge.svg?branch=master)](/actions/workflows/main.yml)
[![K8s integration](/actions/workflows/integration.yml/badge.svg)](/actions/workflows/integration.yml)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
![GitHub](https://img.shields.io/badge/fastapi-v.0.88.0-blue)
![GitHub](https://img.shields.io/badge/python-3.8%20%7C%203.9%20%7C%203.10%20%7C%203.11-blue)
![GitHub](https://img.shields.io/badge/license-no-blue)

---

### Documentation


You should have documentation deployed to your project GitHub pages via [Build Docs workflow](/actions/workflows/docs.yml)

**NOTE!** You might need to enable GitHub pages for this project first.

To build docs manually:
```shell
make docs
```

Use poetry version `1.3.2` and python version `3.10`. Before running `make install` or `poetry install`, fetch git submodule `common` as it is set as package here.

Then open `./site/index.html` with any browser.

## License

This project is licensed under the terms of the SSPL license.
