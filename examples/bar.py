from lightning.app.utilities.network import LightningClient

import lightning_sdk.utils as utils
from lightning_sdk import Studio

client = LightningClient()
ret = utils.get_org(client, org='Lightning AI')
print(ret)

ret = utils.get_teamspace(client, Teamspace="thunder", org="Lightning AI")
print(ret)

ret = utils.get_studio(client, name="impressive-purple-nf4e", Teamspace="thunder", org="Lightning AI")
print(ret)

# ret = utils.create_studio(client, name="test-studio-1", Teamspace="thunder", org="Lightning AI")
# print(ret)


studio = Studio(name="impressive-purple-nf4e", Teamspace="thunder", org="Lightning AI")
print(studio.status)
