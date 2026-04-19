This file contains coding standards and practices for use within this project.

- *Use modern Python.*  Use the latest stable version of Python3 by default.
- *Follow PEP-8.*  Use [PEP 8](https://peps.python.org/pep-0008/) formatting by default.
- *Use type hinting.*  Use [PEP 484](https://peps.python.org/pep-0484/) type hinting.
- *Use `uv`.*  Use `uv` for all dependency management purposes including Python interpreter, libraries, and execution of scripts or parts of the progam.
- *Use dependency cooldowns in `uv`.*  Explicitly set the `exclude-newer` option in `tool.uv` to `P3D`.
- *Use `pytest` for tests.*  Doctests are acceptable only where necessary for good documentation.
- *Use `hypothesis` for property-based testing.*  Particularly where the specifications or code is of a declarative nature, use property-based testing to verify correctness.