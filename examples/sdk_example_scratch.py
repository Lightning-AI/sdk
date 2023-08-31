from lightning_sdk import Studio, Machine

s = Studio("sdk-test-studio-12", "growth", "lightning-ai")
s.start()
s.switch_machine(Machine.T4)
print(s.run("nvidia-smi"))
s.stop()
