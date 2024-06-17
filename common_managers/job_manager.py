import asyncio
from typing import Callable


class JobManager:
    """Class to manage the active jobs in the bot.
    Each job is asynchronous and can be stopped using an event. The class provides methods to add, remove and stop jobs.

    Attributes:
    -----------
    active_jobs: dict[str, list[tuple]]
        Dictionary to store the active jobs. The key is the chat_id and the value is a list of tuples.
        Each tuple contains the job and the stop event.
    """

    def __init__(self):
        self.active_jobs: dict[str, list[tuple]] = dict()

    def __del__(self):
        self.stop_all_jobs()

    def __contains__(self, chat_id: str) -> bool:
        return chat_id in self.active_jobs

    def add_job(self, chat_id: str, task: Callable, *args, **kwargs) -> asyncio.Task:
        """Add a job to the active jobs list.
        Each job is a tuple of the task and the stop event.

        Args:
        -----
        chat_id: str
            The chat_id of the user
        task: Callable
            The task to be executed

        Returns:
        --------
        job: asyncio.Task
            The job that was added to the active jobs list
        """
        stop_event = asyncio.Event()
        job = asyncio.create_task(task(*args, **kwargs, stop_event=stop_event))
        if chat_id not in self.active_jobs:
            self.active_jobs[chat_id] = []
        self.active_jobs[chat_id].append((job, stop_event))
        return job

    def remove_job(self, chat_id: str):
        """Remove a job from the active jobs list.
        All the jobs associated with the chat_id are stopped.

        Args:
        -----
        chat_id: str
            The chat_id of the user
        """
        if chat_id in self.active_jobs:
            for job in self.active_jobs[chat_id]:
                job[1].set()
            self.active_jobs.pop(chat_id)

    def stop_all_jobs(self):
        """Stop all the active jobs."""
        for job_id in self.active_jobs:
            for job in self.active_jobs[job_id]:
                job[1].set()
                job[0].cancel()
        self.active_jobs.clear()

    def get_job_list(self, job_id: str) -> list[tuple]:
        """Get the list of jobs associated with a chat_id.

        Args:
        -----
        job_id: str
            The chat_id of the user

        Returns:
        --------
        list[tuple]
            The list of jobs associated with the chat_id. Each tuple contains the job and the stop event.
        """
        return self.active_jobs[job_id]

    def is_empty(self, chat_id: str) -> bool:
        """Check if there are no active jobs associated with a chat_id."""
        return chat_id not in self.active_jobs
