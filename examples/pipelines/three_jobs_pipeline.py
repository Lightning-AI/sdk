from lightning_sdk.pipeline import Pipeline, JobStep
from lightning_sdk.machine import Machine

pipeline = Pipeline(name='three_jobs_pipeline')
pipeline.run(
  steps=[
      JobStep(
        name='job-1',
        image="ubuntu:latest",
        machine=Machine.CPU,
        command="sleep 9 && echo 'Hello, World!'"
      ),
      JobStep(
          name='job-2',
          image="ubuntu:latest",
          machine=Machine.CPU,
          command="sleep 9 && echo 'Hello, World!'",
          wait_for=None
      ),
      JobStep(
          name='job-3',
          image="ubuntu:latest",
          machine=Machine.CPU,
          command="sleep 9 && echo 'Hello, World!'",
      ),
  ]
)
