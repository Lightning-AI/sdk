from lightning_sdk import Machine, Studio

s = Studio("sdk-test-studio-2", "growth", "lightning-ai", create_ok=True)

print("starting studio...")
s.start()
print(s.machine)

print("switching studio machine...")
s.switch_machine(Machine.A10G)
print(s.machine)

print(s.status)

print(s.run("nvidia-smi"))

print("Stopping Studio")
s.stop()

s.delete()
