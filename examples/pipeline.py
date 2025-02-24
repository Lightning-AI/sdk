from lightning_sdk.pipeline import Pipeline, Job, Deployment
from lightning_sdk.machine import Machine

pipeline = Pipeline(name='first-pipeline')
pipeline.run(
    steps=[
        Job(
            name='job-1',
            image="ubuntu:latest",
            machine=Machine.CPU,
            command="echo 'Hello, World!'",
        ),
        Job(
            name='job-2',
            image="ubuntu:latest",
            machine=Machine.CPU,
            command="echo 'Hello, World!'",
            needs=None,
        ),
        Job(
            name='job-3',
            image="ubuntu:latest",
            machine=Machine.CPU,
            command="echo 'Hello, World!'",
        ),
    ]
)

pipeline = Pipeline(name='second-pipeline')
pipeline.run(
    steps=[
        Deployment(
            name='deployment-1',
            image="nginx",
            machine=Machine.CPU,
        ),
    ]
)
