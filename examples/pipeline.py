from lightning_sdk.pipeline import Pipeline, Job, Deployment, Studio

studio = Studio(name="train_and_deploy")
studio.start()
studio.run("git clone https://github.com/tchaton/pipeline_demo.git")

pipeline = Pipeline(name='train_and_deploy', studio=studio)
pipeline.run(
    steps=[
        Job(command="python pipeline_demo/train.py"),
        Deployment(command="python pipeline_demo/server.py", ports=[8000]),
    ],
)
