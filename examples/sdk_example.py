import lightning_sdk as L

Teamspace = L.Teamspace()

# TODO: studio needs
# a. a Teamspace arg
# b. access through the Teamspace

studio = L.Studio()

# init
studio = L.Studio()
studio.start()
studio.switch_machine("4xA10g")
studio.stop()
studio.delete()

# TODO: get status

# can run arbitrary commands
studio.run(["curl X", "echo any chain of commands"])

# call any app on the studio
model_server_app = studio.app("model-server")  # machine not needed here, needed in args
# model_server_app.execute(cm='a-command', args={k: v, k2: v2})
model_server_app.run(cm="app-command", args={k: v, k2: v2})  # TODO: this will allow to stop jobs

# init
new_studio = L.Studio()
existing_studio = L.Studio(
    "existing-studio-name"
)  # TODO: This is not just existing, I want to be able to start a new one

new_studio = L.new_studio("studio-name")
existing_studio = L.Studio("studio-name", new=False)

# after all it doesn't matter if it's existing: if it exists and it's stopped we will start it anyway

# if name not provided, then choose a new one
# the only thing we need is a .name property and an .exists() predicate
new_studio = L.Studio("studio-name")


# init
Teamspace = L.Teamspace()  # TODO: need to pass name here

# data
Teamspace.drive.upload(source="a/path", dest="studios/abc")
Teamspace.drive.download(source="studios/studio/path", dest="local/path")
Teamspace.drive.mv(source="studios/studio/path", dest="local/path")

Teamspace.drive.s3.add("bucket-name", "alias")
Teamspace.drive.s3.remove("bucket-name", "alias")

# properties
Teamspace.studios  # returns list of objects
Teamspace.jobs  # returns lisdt of jobs

existing_job = L.Job("job name")


# TODO: org, jobs
