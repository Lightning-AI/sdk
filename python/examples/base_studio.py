from lightning_sdk.base_studio import BaseStudio

# base studio class without specific template
base_studio_class = BaseStudio(org="default-org")

# List all base studios in the specified organization
base_studio_class.list()
# {'templates': [{'id': 'cet-template-id', 'name': 'test-template-1'...},...}]}

# Base studio with specific template
base_studio = BaseStudio(name="test-template-id", org="default-org")

# Update the base studio with new configurations
base_studio.update(
    name="test-template-2",
)
# {'id': 'cet-template-id', 'name': 'test-template-2'...}
