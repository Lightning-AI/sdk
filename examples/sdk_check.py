from lightning_sdk import Teamspace, Studio


def example1():
    ts = Teamspace(name="thunder", org="Lightning AI")
    studio = ts.studio(name="foobar")
    studio.start()
    print(studio.status)


def example2():
    studio = Studio(name="foobar", Teamspace="thunder", org="Lightning AI")
    print(studio.status)


if __name__ == "__main__":
    example1()
    # example2()