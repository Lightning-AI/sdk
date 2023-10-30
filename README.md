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

# or s =  Studio("my-studio", "my-teamspace", org="my-org", create_ok=True)
# or (inside a Studio) s = Studio()  # will infer name, teamspace and owner of the current studio automatically.
#    can also just pass some arguments: s = Studio("my-new-studio", create_ok=True)
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

# install plugins for jobs and multi-machine training
s.install_plugin("jobs")
s.install_plugin("multi-machine-training")

# run the resulting plugins to start 1 job and 1 multi-machine training
s.installed_plugins["jobs"].run("python my_dummy_file", name="my_first_job", cloud_compute=Machine.A10G)
s.installed_plugins["multi-machine-training"].run("python my_dummy_file", name="my_first_mmt", cloud_compute=Machine.T4, num_instances=42)

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
