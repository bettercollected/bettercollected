{ lib
, python
, poetry2nix
}:

poetry2nix.mkPoetryApplication {
  inherit python;

  projectDir = ./.;
  pyproject = ./pyproject.toml;
  poetrylock = ./poetry.lock;

  pythonImportsCheck = [ "bettercollected_backend_server" ];

  meta = with lib; {
    homepage = "";
    description = "";
  };
}
