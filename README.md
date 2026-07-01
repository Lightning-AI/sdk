# Lightning SDK

Software Development Kit (SDK) for Lightning AI.

This repository is a monorepo: the published Python package (**`lightning-sdk`**, import name `lightning_sdk`) lives under [`python/`](python/), alongside tests and Sphinx docs. Packaging metadata (`pyproject.toml`, `setup.py`) is in [`python/`](python/) as well. To hack on it locally, from the repository root run **`pip install -e ./python`** (or `cd python && pip install -e .`).

## Installation

Install from PyPI:

```bash
pip install lightning-sdk
```

## Usage

Export `LIGHTNING_USER_ID` and `LIGHTNING_API_KEY` from your account settings → Keys → Programmatic Login.

Inside a Studio, those variables are usually already set.

## Example

```python
from lightning_sdk import Machine, Studio

# or s =  Studio("my-studio", "my-teamspace", org="my-org", create_ok=True)
# or (inside a Studio) s = Studio()  # will infer name, teamspace and owner of the current studio automatically.
#    can also just pass some arguments: s = Studio("my-new-studio", create_ok=True)
s = Studio("my-studio", "my-teamspace", user="my-username", create_ok=True)

print("starting Studio...")
s.start()

# prints Machine.CPU-4
print(s.machine)

# or start directly on this machine with s.start(Machine.L4)
print("switching Studio machine...")
s.switch_machine(Machine.L4)

# prints Machine.L4
print(s.machine)

# prints Status.Running
print(s.status)

print(s.run("nvidia-smi"))

print("Stopping Studio")
s.stop()

# duplicates Studio, this will also duplicate the environment and all files in the Studio
duplicate = s.duplicate()

# delete original Studio, duplicated Studio is it's own entity and not related to original anymore
s.delete()

# stop and delete duplicated Studio
duplicate.stop()
duplicate.delete()
```

## JavaScript

Additional client SDKs (for example JavaScript) can live alongside `python/` as this repo grows.
