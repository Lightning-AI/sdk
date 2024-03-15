from lightning_sdk.services import Client


class ScrapeWebsitesFromURLs(Client):
    def __init__(self) -> None:
        super().__init__(
            teamspace_id="01hrvpgvmv47jge4rjjndf26cs",
            file_endpoint_teamspace_id="01hrvpgvmv47jge4rjjndf26cs",
            file_endpoint_id="01hrvqzkzhs999wmb30ke481e3",
        )


client = ScrapeWebsitesFromURLs()
client.run(output_dir="output_dir", data_path="example.csv")
