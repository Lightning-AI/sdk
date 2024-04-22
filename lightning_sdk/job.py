from lightning_sdk.api.job_api import JobApi
from lightning_sdk.status import Status
from lightning_sdk.studio import Studio


class Job:
    def __init__(self, job_name: str, studio: Studio) -> None:
        self.job_name = job_name
        self.studio = studio
        self._job_api = JobApi()

        try:
            self._job = self._job_api.get_job(job_name, self.studio.teamspace.id)
        except ValueError as e:
            raise ValueError(f"Job {job_name} does not exist in Teamspace {self.studio.teamspace.name}") from e

    @property
    def status(self) -> Status:
        try:
            status = self._job_api.get_job_status(self._job.id, self.studio.teamspace.id)
            return _internal_status_to_external_status(status)
        except Exception:
            raise RuntimeError(
                f"Job {self.job_name} does not exist in Teamspace {self.studio.teamspace.name}. Did you delete it?"
            ) from None

    def stop(self) -> None:
        if self.status in (Status.Stopped, Status.Failed):
            return None

        return self._job_api.stop_job(self._job.id, self.studio.teamspace.id)

    def delete(self) -> None:
        self._job_api.delete_job(self._job.id, self.studio.teamspace.id)


def _internal_status_to_external_status(internal_status: str) -> Status:
    """Converts internal status strings from HTTP requests to external enums."""
    return {
        # don't get a status if no instance alive
        None: Status.Stopped,
        # TODO: should we have deleted in here?
        "LIGHTNINGAPP_INSTANCE_STATE_UNSPECIFIED": Status.Pending,
        "LIGHTNINGAPP_INSTANCE_STATE_IMAGE_BUILDING": Status.Pending,
        "LIGHTNINGAPP_INSTANCE_STATE_NOT_STARTED": Status.Pending,
        "LIGHTNINGAPP_INSTANCE_STATE_PENDING": Status.Pending,
        "LIGHTNINGAPP_INSTANCE_STATE_RUNNING": Status.Running,
        "LIGHTNINGAPP_INSTANCE_STATE_FAILED": Status.Failed,
        "LIGHTNINGAPP_INSTANCE_STATE_STOPPED": Status.Stopped,
        "LIGHTNINGAPP_INSTANCE_STATE_COMPLETED": Status.Stopped,
    }[internal_status]
