##########################################################################
# Hopla - Copyright (C) AGrigis, 2015 - 2025
# Distributed under the terms of the CeCILL-B license, as published by
# the CEA-CNRS-INRIA. Refer to the LICENSE file or to
# http://www.cecill.info/licences/Licence_CeCILL-B_V1-en.html
# for details.
##########################################################################

"""
Contains PBS specific functions.
"""

import copy
import json
import os
import shutil
import subprocess
import textwrap
import traceback
import warnings
from pathlib import Path

from .utils import DelayedJob, InfoWatcher, format_attributes


class CCCInfoWatcher(InfoWatcher):
    """ An instance of this class is shared by all jobs, and is in charge of
    calling ccc to check status for all jobs at once.

    Parameters
    ----------
    delay_s: int, default 60
        maximum delay before each non-forced call to the cluster.
    """
    def __init__(self, delay_s=60):
        super().__init__(delay_s)

    @property
    def update_command(self):
        """ Return the command to list jobs status.
        """
        active_jobs = self._registered - self._finished
        return "squeue --states=all --json -j " + ",".join(active_jobs)

    @property
    def valid_status(self):
        """ Return the list of valid status.
        """
        return ["RUNNING", "PENDING", "SUSPENDED", "COMPLETING", "CONFIGURING",
                "UNKNOWN"]

    @classmethod
    def read_info(cls, string):
        """ Reads the output of squeue and returns a dictionary containing
        main jobs information.
        """
        if not isinstance(string, str):
            string = string.decode()
        all_stats = {str(val["job_id"]): val
                     for val in json.loads(string)["jobs"]}
        return all_stats


class DelayedCCCJob(DelayedJob):
    """ Represents a job that have been queue for submission by an executor,
    but hasn't yet been scheduled.

    Parameters
    ----------
    delayed_submission: DelayedSubmission
        a delayed submission allowing to generate the command line to
        execute.
    executor: Executor
        base job executor.
    job_id: str
        the job identifier.
    backend: str, default 'flux'
        the multi-taks backend to use: 'flux', 'joblib' or 'oneshot'.

    Raises
    ------
    ValueError
        If an invalid backend is specified.
    """
    _hub = "n4h00001rs"
    _submission_cmd = "ccc_msub"
    _container_cmd = "pcocc-rs run {hub}:{image_name} {params} -- {command}"
    _container_onshot_cmd = (
        "pcocc-rs run --no-ep {hub}:{image_name} {params} /bin/bash -- "
        "-c '/bin/bash {command}'"
    )

    def __init__(self, delayed_submission, executor, job_id, backend="flux"):
        super().__init__(delayed_submission, executor, job_id)
        self.multi_task = isinstance(delayed_submission, (list, tuple))
        if backend not in ("flux", "joblib", "oneshot"):
            raise ValueError(
                "Invalid backend. Valid multi-taks backends are: 'flux', "
                "'joblib' or 'oneshot'."
            )
        self.backend = backend
        resource_dir = Path(__file__).parent / "resources"
        if self.multi_task and self.backend == "flux":
            path = resource_dir / "ccc_multi_batch_template.txt"
            self.worker_file = resource_dir / "worker.sh"
        elif self.multi_task and self.backend == "joblib":
            path = resource_dir / "ccc_batch_template.txt"
            self.worker_file = resource_dir / "joblib_script_template.txt"
        elif self.multi_task and self.backend == "oneshot":
            path = resource_dir / "ccc_batch_template.txt"
            self.worker_file = resource_dir / "oneshot_script_template.txt"
        else:
            path = resource_dir / "ccc_batch_template.txt"
        with open(path) as of:
            self.template = of.read()
        image = self._executor.parameters["image"]
        assert image is not None, "Please select or give an image."
        if os.path.isfile(image):
            self.image_file = image
            self.image_name = os.path.basename(image).split(".")[0]
        else:
            self.image_file = None
            self.image_name = image

    # @property
    # def exitcode(self):
    #     """ Check if the code finished properly.
    #     """
    #     exitcode = True
    #     if self.paths.stdout.exists():
    #         exitcode = self._check_is_done(self.paths.stdout)
    #     if self.paths.stderr.exists():
    #         with open(self.paths.stderr) as of:
    #             content = [line.startswith("+ ") for line in of]
    #             exitcode = exitcode and all(content)
    #     return exitcode

    def generate_batch(self):
        """ Write the batch file.
        """
        params = copy.deepcopy(self._executor.parameters)
        params["walltime"] *= 3600
        params["memory"] *= 1000
        if self.backend == "joblib":
            if params["modules"] != "":
                params["modules"] = f"python3/3.12,{params['modules']}"
            else:
                params["modules"] = "python3/3.12"
        if params["modules"] != "":
            params["modules"] = f"module load {params['modules']}"
        try:
            self.import_image()
        except Exception:
            err = textwrap.indent(traceback.format_exc(), "   |")
            warnings.warn(
                f"Can't import image: {self.image_name}",
                stacklevel=2
            )
            print(err)
        if self.multi_task and self.backend == "flux":
            n_multi_cpus = self._executor.parameters["nmulticpus"]
            shutil.copy(self.worker_file, self.paths.worker_file)
            subcmds = [
                self._container_cmd.format(
                    hub=self._hub,
                    image_name=self.image_name,
                    params=submission.execution_parameters,
                    command=submission.command
                )
                for submission in self.delayed_submission
            ]
            subcmds = [
                f"1-{n_multi_cpus} . {self.paths.worker_file} {command}"
                for command in subcmds
            ]
            params["logdir"] = self.paths.flux_dir
            self.paths.flux_dir.mkdir(parents=True, exist_ok=True)
            with open(self.paths.task_file, "w") as of:
                of.write("\n".join(subcmds))
            cmd = self.paths.task_file
        elif self.multi_task and self.backend == "joblib":
            n_cpus = self._executor.parameters["ncpus"]
            with open(self.worker_file) as of:
                joblib_template = of.read()
            subcmds = [
                self._container_cmd.format(
                    hub=self._hub,
                    image_name=self.image_name,
                    params=submission.execution_parameters,
                    command=submission.command
                )
                for submission in self.delayed_submission
            ]
            subcmds = [
                f"'{command}',"
                for command in subcmds
            ]
            with open(self.paths.joblib_file, "w") as of:
                of.write(
                    joblib_template.format(
                        commands="\n".join(subcmds),
                        njobs=n_cpus,
                    )
                )
            cmd = f"python {self.paths.joblib_file}"
        elif self.multi_task and self.backend == "oneshot":
            with open(self.worker_file) as of:
                oneshot_template = of.read()
            subcmds = [
                submission.command
                for submission in self.delayed_submission
            ]
            subcmds = [
                f"'{command}'"
                for command in subcmds
            ]
            with open(self.paths.oneshot_file, "w") as of:
                of.write(
                    oneshot_template.format(
                        logdir=self.paths.oneshot_dir,
                        commands="\n".join(subcmds),
                    )
                )
            self.paths.oneshot_dir.mkdir(parents=True, exist_ok=True)
            cmd = self._container_onshot_cmd.format(
                hub=self._hub,
                image_name=self.image_name,
                params=self.delayed_submission[0].execution_parameters,
                command=self.paths.oneshot_file
            )
        else:
            cmd = self._container_cmd.format(
                hub=self._hub,
                image_name=self.image_name,
                params=self.delayed_submission.execution_parameters,
                command=self.delayed_submission.command
            )
        with open(self.paths.submission_file, "w") as of:
            if self.paths.stdout.exists():
                os.remove(self.paths.stdout)
            if self.paths.stderr.exists():
                os.remove(self.paths.stderr)
            of.write(
                self.template.format(
                    command=cmd,
                    stdout=self.paths.stdout,
                    stderr=self.paths.stderr,
                    **params
                )
            )

    def import_image(self):
        """ Load the docker image if not available.
        """
        cmd = ["pcocc-rs", "image", "list", "-r", self._hub]
        stdout = subprocess.check_output(cmd)
        if self.image_name not in self.read_index(stdout):
            if self.image_file is None:
                raise ValueError(
                    f"'{self.image_name}' image not available! Please "
                    "consider providing the image archive.")
            cmd = [
                "pcocc-rs", "image", "import",
                f"docker-archive:{self.image_file}",
                f"{self._hub}:{self.image_name}"]
            subprocess.check_call(cmd)

    @classmethod
    def read_index(cls, string):
        """ Reads the output of of pcocc-rs image list and returns a
        list available container.
        """
        if not isinstance(string, str):
            string = string.decode()
        names = [item.strip().split(" ")[0]
                 for item in string.split("\n")[2:-2]]
        return names

    def read_jobid(self, string):
        """ Return the started job ID.
        """
        if not isinstance(string, str):
            string = string.decode()
        return string.rstrip("\n").strip().split(" ")[-1]

    def sub_report(self):
        report = []
        prefix = f"{self.__class__.__name__}<job_id={self.job_id}>"
        if self.multi_task and self.backend == "flux":
            log_files = list(self.paths.flux_dir.glob("bulk_*"))
            tasks_ids = [
                path.name.split("_")[1]
                for path in log_files
                if not self._check_is_done(path)
            ]
            report.append(
                f"{prefix}number_of_tasks: {len(self.delayed_submission)}")
            report.append(f"{prefix}failed_tasks: {tasks_ids}")
            report.append(f"{prefix}running_tasks: {len(log_files)}")
            report.append(f"{prefix}logdir: {self.paths.flux_dir}")
        elif self.multi_task and self.backend == "oneshot":
            log_files = list(self.paths.flux_dir.glob("job_*.exitcode"))
            exitcodes = []
            for path in log_files:
                with open(path) as of:
                    exitcodes.append(int(of.read().strip()))
            n_fail = sum(1 for code in exitcodes if code != 0)
            n_submissions = len(self.delayed_submission)
            n_tasks = len(log_files)
            report.append(f"{prefix}number_of_tasks: {n_submissions}")
            report.append(f"{prefix}failed_tasks: {n_fail}")
            report.append(f"{prefix}running_tasks: {n_tasks}")
            report.append(f"{prefix}logdir: {self.paths.oneshot_dir}")
        return report

    @property
    def start_command(self):
        """ Return the start job command.
        """
        return type(self)._submission_cmd

    @property
    def stop_command(self):
        """ Return the stop job command.
        """
        return "ccc_mqdel"

    def __repr__(self):
        return format_attributes(
            self,
            attrs=["job_id", "submission_id", "_hub", "image_name"]
        )
