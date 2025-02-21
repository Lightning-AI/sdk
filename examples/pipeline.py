from lightning_sdk.pipeline import Pipeline, Job
from lightning_sdk.machine import Machine

pipeline = Pipeline(name='first-pipeline')
pipeline.run(
    steps=[
        Job(
            name='job-1',
            image="ubuntu:latest",
            machine=Machine.CPU,
            command="echo 'Hello, World!'",
            cloud_account="test-8"
        ),
    ]
)
