##########################################################################
# Hopla - Copyright (C) AGrigis, 2015 - 2025
# Distributed under the terms of the CeCILL-B license, as published by
# the CEA-CNRS-INRIA. Refer to the LICENSE file or to
# http://www.cecill.info/licences/Licence_CeCILL-B_V1-en.html
# for details.
##########################################################################

"""
Contains job execution functions.
"""

import time
from pathlib import Path

from tqdm import tqdm

from .ccc import (
    CCCInfoWatcher,
    DelayedCCCJob,
)
from .config import (
    DEFAULT_OPTIONS,
    hopla_options,
)
from .pbs import (
    DelayedPbsJob,
    PbsInfoWatcher,
)
from .slurm import (
    DelayedSlurmJob,
    SlurmInfoWatcher,
)
from .utils import format_attributes


class Executor:
    """ Base job executor.

    Parameters
    ----------
    cluster: str
        the type of cluster: 'slurm', 'ccc', 'pbs'.
    folder: Path/str
        folder for storing job submission/output and logs.
    queue: str
        the name of the queue where the jobs will be submitted.
    image: str
        path to a docker '.tar' image or apptainer '.simg' image or name of
        an existing image.
    name: str, default 'hopla'
        the name of the submitted jobs.
    memory: float , default 2
        the memory allocated to each job (in GB).
    walltime: int default 72
        the walltime used for each job (in hours).
    n_cpus: int, default 1
        the number of cores allocated for each job.
    n_gpus: int, default 0
        the number of GPUs allocated for each job.
    n_multi_cpus: int, default 1
        the number of cores reserved for each multi-tasks job.
    modules: list of str, default None
        the environment modules to be loaded.
    project_id: str, default None
        the project ID where you have computing hours.
    backend: str, default 'flux'
        the multi-taks backend to use: 'flux', 'joblib or 'oneshot'. This
        option is only used with CCC cluster type.

    Examples
    --------
    >>> import hopla
    >>> executor = hopla.Executor(
    ...     cluster="slurm",
    ...     folder="/tmp/hopla",
    ...     queue="Nspin_long",
    ...     image="/tmp/hopla/my-apptainer-img.simg",
    ... )
    >>> jobs = [executor.submit("sleep", k) for k in range(1, 11)]
    >>> executor(max_jobs=2) # doctest: +SKIP
    >>> print(executor.report) # doctest: +SKIP

    Raises
    ------
    ValueError
        If the cluster type is not supported.
    """
    _delay_s = 60
    _counter = 0
    _start = time.time()

    def __init__(self, cluster, folder, queue, image, name="hopla", memory=2,
                 walltime=72, n_cpus=1, n_gpus=0, n_multi_cpus=1, modules=None,
                 project_id=None, backend="flux"):
        if cluster == "pbs":
            self._job_class = DelayedPbsJob
            self._watcher_class = PbsInfoWatcher
        elif cluster == "ccc":
            self._job_class = DelayedCCCJob
            self._watcher_class = CCCInfoWatcher
        elif cluster == "slurm":
            self._job_class = DelayedSlurmJob
            self._watcher_class = SlurmInfoWatcher
        else:
            raise ValueError(
                f"Unsupported cluster type: {cluster}"
            )
        self.backend = backend
        self.watcher = self._watcher_class(self._delay_s)
        self.folder = Path(folder).expanduser().absolute()
        modules = modules or []
        self.parameters = {
            "name": name,
            "queue": queue,
            "memory": memory,
            "walltime": walltime,
            "ncpus": n_cpus,
            "nmulticpus": n_multi_cpus,
            "ngpus": n_gpus,
            "modules": ",".join(modules),
            "image": (
                Path(image).expanduser().absolute()
                if Path(image).is_file()
                else image
            ),
            "project_id": project_id
        }
        self._delayed_jobs = []

    def __call__(self, max_jobs=300):
        """ Run jobs controlling the maximum number of concurrent submissions.

        Parameters
        ----------
        max_jobs: int, default 300
            the maximum number of concurrent submissions.
        """
        opts = hopla_options.get()
        verbose = opts.get("verbose", DEFAULT_OPTIONS["verbose"])
        dryrun = opts.get("dryrun", DEFAULT_OPTIONS["dryrun"])
        self._delay_s = opts.get("delay_s", DEFAULT_OPTIONS["delay_s"])
        self.watcher._delay_s = self._delay_s

        _start = 0
        desc = self._job_class._submission_cmd.upper()
        pbar = tqdm(total=self.n_jobs, desc=desc)
        while (self.n_waiting_jobs != 0 or
               not all(job.done for job in self._delayed_jobs)):
            if verbose:
                print(self.status)
                # print(self._delayed_jobs)
            if self.n_waiting_jobs != 0 and self.n_running_jobs < max_jobs:
                _delta = max_jobs - self.n_running_jobs
                _stop = _start + _delta
                for job in self._delayed_jobs[_start:_stop]:
                    assert job.status == "NOTSTARTED"
                    job.start(dryrun=dryrun)
                    pbar.update(1)
                    pbar.refresh()
                _start = _stop
            time.sleep(self._delay_s)
        pbar.close()
        self.watcher.update()

    def submit(self, script, *args, execution_parameters=None, **kwargs):
        """ Create a delayed job.

        Parameters
        ----------
        script: Path/str or list of DelayedSubmission
            script(s) to execute.
        *args: any positional argument of the script.
        execution_parameters: str
            parameters passed to the container during execution.
        **kwargs: any named argument of the script.

        Returns
        -------
        job: DelayedJob
            a job instance.

        Raises
        ------
        RuntimeError
            If the job class is not DelayedCCCJob for multi-tasks submission.
        """
        self._counter += 1
        if isinstance(script, (list, tuple)):
            if self._job_class != DelayedCCCJob:
                raise RuntimeError(
                    "Submitting many jobs inside an allocation only supported "
                    "with CCC."
                )
            job = self._job_class(
                script,
                self,
                self._counter,
                backend=self.backend,
            )
        else:
            job = self._job_class(
                DelayedSubmission(
                    script,
                    *args,
                    execution_parameters=execution_parameters,
                    **kwargs
                ),
                self,
                self._counter
            )
        self._delayed_jobs.append(job)
        return job

    @property
    def status(self):
        """ Display current status.
        """
        message = ["-" * 40]
        message += [
            f"{self.__class__.__name__}<time={time.time() - self._start}>"
        ]
        message += [f"- jobs: {self.n_jobs}"]
        message += [f"- done: {self.n_done_jobs}"]
        message += [f"- running: {self.n_running_jobs}"]
        message += [f"- waiting: {self.n_waiting_jobs}"]
        return "\n".join(message)

    @property
    def report(self):
        """ Generate a general report for all jobs.
        """
        message = [job.report for job in self._delayed_jobs]
        return "\n".join(message)

    @property
    def n_jobs(self):
        """ Get the number of stacked jobs.
        """
        return len(self._delayed_jobs)

    @property
    def n_done_jobs(self):
        """ Get the number of finished jobs.
        """
        return sum([job.done for job in self._delayed_jobs])

    @property
    def n_waiting_jobs(self):
        """ Get the number of waiting jobs.
        """
        return sum([job.status == "NOTSTARTED" for job in self._delayed_jobs])

    @property
    def n_running_jobs(self):
        """ Get the number of running jobs.
        """
        return self.n_jobs - self.n_done_jobs - self.n_waiting_jobs


class DelayedSubmission:
    """ Object for specifying the submit parameters for further processing.
    """
    def __init__(self, script, *args, execution_parameters=None, **kwargs):
        self.script = script
        self.args = args
        self.execution_parameters = execution_parameters or ""
        self.kwargs = kwargs

    @property
    def command(self):
        """ Return the command to execute.
        """
        command = [self.script]
        command += [str(e) for e in self.args]
        command += [f"-{key} {val}" for key, val in self.kwargs.items()]
        return " ".join(command)

    def __repr__(self):
        return format_attributes(
            self,
            attrs=["command", "execution_parameters"]
        )
