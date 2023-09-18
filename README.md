# Lightning SDK

Software Development Kit (SDK) for Lightning AI

## Installation

The package can be installed using `pip install --index-url https://test.pypi.org/simple/ lightning-sdk`

## Usage
To use the SDK, you need to export the environment variables `LIGHTNING_USER_ID` and `LIGHTNING_API_KEY` with the values found in your account settings -> Keys -> Programmatic Login.

If you want to use it from within a Studio, these variables are already available for you.

## Example

```python
from lightning_sdk import Machine, Studio

s = Studio("my-studio", "my-teamspace", user="my-username", create_ok=True)

print("starting Studio...")
s.start()

# prints Machine.CPU-4
print(s.machine)

print("switching Studio machine...")
s.switch_machine(Machine.A10G)

# prints Machine.A10G
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