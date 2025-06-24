from lightning_sdk.pipeline import Pipeline, JobStep, Studio, DeploymentReleaseStep

studio = Studio(name="train_and_deploy")
studio.start()
studio.run("git clone https://github.com/tchaton/pipeline_demo.git")

pipeline = Pipeline(name='train_and_deploy', studio=studio)
pipeline.run(
    steps=[
        JobStep(
            name="train-step",
            command="python pipeline_demo/train.py"
        ),
        DeploymentReleaseStep(
            name='deploy-step',
            deployment_name="deploy-prod",
            command="python pipeline_demo/server.py",
            ports=[8000]
        ),
    ],
)
