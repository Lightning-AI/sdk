import subprocess
from typing import Any, Optional, Union


class _LegacyLightningCLI:
    """Legacy CLI for `fabric run model` and `lightning run app`."""

    def model(
        self,
        script: str,
        accelerator: Optional[str] = None,
        strategy: Optional[str] = None,
        devices: str = "1",
        num_nodes: int = 1,
        node_rank: int = 0,
        main_address: str = "127.0.0.1",
        main_port: int = 29400,
        precision: Optional[Union[int, str]] = None,
        *script_args: Any,
    ) -> None:
        """Legacy CLI for `fabric run model`.

        Args:
            script: The script containing the fabric definition to launch
            accelerator: The hardware accelerator to run on.
            strategy: Strategy for how to run across multiple devices.
            devices: Number of devices to run on (``int``), which devices to run on (``list`` or ``str``),
                or ``'auto'``. The value applies per node.
            num_nodes: Number of machines (nodes) for distributed execution.
            node_rank: The index of the machine (node) this command gets started on.
                Must be a number in the range 0, ..., num_nodes - 1.
            main_address: The hostname or IP address of the main machine (usually the one with node_rank = 0).
            main_port: The main port to connect to the main machine.
            precision: Double precision (``64-true`` or ``64``), full precision (``32-true`` or ``64``),
                half precision (``16-mixed`` or ``16``) or bfloat16 precision (``bf16-mixed`` or ``bf16``)
            script_args: Arguments passed to the script to execute

        """
        print(
            "lightning run model is deprecated and will be removed in future versions."
            " Please call `fabric run model` instead."
        )

        args = []
        if accelerator is not None:
            args.extend(["--accelerator", accelerator])

        if strategy is not None:
            args.extend(["--strategy", strategy])

        args.extend(["--devices", devices])
        args.extend(["--num_nodes", num_nodes])
        args.extend(["--node_rank", node_rank])
        args.extend(["--main_address", main_address])
        args.extend(["--main_port", main_port])

        if precision is not None:
            args.extend(["--precision", precision])

        args.extend(list(script_args))
        subprocess.run(["fabric", "run", "model", script, *args])

    def app(
        self,
        file: str,
        cloud: bool = False,
        name: str = "",
        without_server: bool = False,
        no_cache: bool = False,
        blocking: bool = False,
        open_ui: bool = False,
        env: str = "",
        secret: str = "",
        app_args: str = "",
        setup: str = "",
        enable_basic_auth: str = "",
    ) -> None:
        """Legacy CLI for `lightning_app run app`.

        Args:
            file: The file containing your application
            cloud: Run the app in the cloud
            name: The current application name
            without_server: Run without server
            no_cache: Disable caching of packages installed from requirements.txt
            blocking: Don't block
            open_ui: Decide whether to launch the app UI in a web browser
            env: Environment variables to be set for the app.
            secret: Secret variables to be set for the app.
            app_args: Collection of arguments for the app.
            setup: run environment setup commands from the app comments
            enable_basic_auth: Enable basic authentication for the app and use credentials provided in the format
                username:password

        """
        print(
            "lightning run app is deprecated and will be removed in future versions."
            " Please call `lightning_app run app` instead."
        )
        args = []

        if cloud:
            args.append("--cloud")

        if name:
            args.extend(["--name", name])

        if without_server:
            args.append("--without-server")

        if no_cache:
            args.append("--no-cache")

        if blocking:
            args.append("--blocking")

        if open_ui:
            args.append("--open-ui")

        if env:
            args.extend(["--env", env])

        if secret:
            args.extend(["--secret", secret])

        if app_args:
            args.extend(["--app_args", app_args])

        if setup:
            args.extend(["--setup", setup])

        if enable_basic_auth:
            args.extend(["--enable-basic-auth", enable_basic_auth])

        subprocess.run(["lightning_app", "run", "app", file, *args])
