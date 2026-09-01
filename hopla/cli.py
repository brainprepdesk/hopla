##########################################################################
# Hopla - Copyright (C) AGrigis, 2015 - 2025
# Distributed under the terms of the CeCILL-B license, as published by
# the CEA-CNRS-INRIA. Refer to the LICENSE file or to
# http://www.cecill.info/licences/Licence_CeCILL-B_V1-en.html
# for details.
##########################################################################

import argparse
import datetime
import re
import shlex
import shutil

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:
    import tomli as tomllib
from pathlib import Path

import numpy as np
import pandas as pd

import hopla
from hopla.config import Config

# Colors (ANSI)
RESET = "\033[0m"
BOLD = "\033[1m"
CYAN = "\033[36m"
MAGENTA = "\033[35m"
DIM = "\033[2m"


def print_header(
        license="CeCILL-B",
        subtitle="Fast, friendly CLI to submit your jobs"):
    """
    Print a styled header banner for the hoplacli tool.

    Parameters
    ----------
    license : str, optional
        The license displayed in the header. Default is "CeCILL-B".
    subtitle : str, optional
        A secondary line of text displayed below the title.
        Default is "Fast, friendly CLI to submit you jobs".

    Returns
    -------
    None

    Notes
    -----
    - The header is styled with ANSI escape codes for colors and bold text.
    - The width of the banner adapts to the terminal size (up to 100
      characters).
    - Includes a timestamp of when the session started.
    - Uses box-drawing characters for a clean framed look.
    """
    # Terminal width
    width = shutil.get_terminal_size((80, 20)).columns
    max_content = min(width - 6, 100)  # keep borders tidy

    # Banner text
    banner = f"{BOLD}{MAGENTA}HOPLA{RESET} {BOLD}{CYAN}CLI{RESET}"
    meta = f"{DIM}{datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}{RESET}"

    # Compose lines (truncate if needed)
    def clip(s): return (s[:max_content] + "…" if len(s) > max_content else s)
    line1 = clip(banner)
    line2 = clip(f"{BOLD}License: {license}{RESET}")
    line3 = clip(subtitle)
    line4 = clip(f"Session started • {meta}")

    # Box drawing
    top = "╭" + "─" * (max_content + 2) + "╮"
    bottom = "╰" + "─" * (max_content + 2) + "╯"

    def center(s):
        pad = max_content - len(_strip_ansi(s))
        left = pad // 2
        right = pad - left
        return "│ " + (" " * left) + s + (" " * right) + " │"

    print(top)
    print(center(line1))
    print(center(line2))
    print(center(line3))
    print(center(line4))
    print(bottom)
    print()


def print_toml(
        data,
        title="TOML Configuration"):
    """
    Pretty-print TOML content inside a styled box with colors.

    Parameters
    ----------
    data : dict
        TOML data content.
    title : str, optional
        Title displayed at the top of the box. Default is "TOML Configuration".

    Notes
    -----
    - Uses ANSI escape codes for colors.
    - Automatically adapts to terminal width (up to 100 characters).
    - Displays keys in cyan and values in magenta for readability.
    """
    # Terminal width
    width = shutil.get_terminal_size((80, 20)).columns
    max_content = min(width - 6, 100)

    # Box drawing
    top = "╭" + "─" * (max_content + 2) + "╮"
    bottom = "╰" + "─" * (max_content + 2) + "╯"

    def center(s):
        pad = max_content - len(_strip_ansi(s))
        left = pad // 2
        right = pad - left
        return "│ " + (" " * left) + s + (" " * right) + " │"

    def format_line(key, value=None):
        if value is None:
            line = f"{CYAN}{key}{RESET}"
        else:
            line = f"{CYAN}{key}{RESET} = {MAGENTA}{value}{RESET}"
        visible_len = len(_strip_ansi(line))
        if visible_len > max_content:
            line = line[:max_content-1] + "…"
            visible_len = len(_strip_ansi(line))
        return "│ " + line + " " * (max_content - visible_len) + " │"

    # Print box
    print(top)
    print(center(f"{BOLD}{title}{RESET}"))
    print("│ " + " " * max_content + " │")
    for section, content in data.items():
        if isinstance(content, dict):
            print(format_line(f"[{section}]"))
            for k, v in content.items():
                print(format_line(k, v))
        else:
            print(format_line(section, content))
        print(format_line(""))

    print(bottom)


def _strip_ansi(s: str) -> str:
    """Remove ANSI escape codes from a string."""
    return re.sub(r"\x1b\[[0-9;]*m", "", s)


def main():
    """
    Command-line interface for automated job execution with hopla.

    This function loads a TOML configuration file, initializes a hopla
    executor, and submits jobs either individually or in chunks depending
    on the configuration. It then runs the executor with a specified maximum
    number of jobs and writes a report to disk.

    Workflow
    --------
    1. Parse CLI arguments using argparse.
    2. Load the TOML configuration file with `tomllib`.
    3. Initialize a `hopla.Executor` with environment parameters.
    4. Extract commands from the configuration:
       - If `multi` is defined, split commands into chunks and submit them
         as delayed submissions.
       - Otherwise, submit commands directly.
    5. Run the executor with the specified maximum number of jobs.
    6. Write a textual report to `report.txt` inside the executor's folder.

    TOML Configuration
    ------------------
    The configuration file is structured into sections:

    [project]
    name : str
        Name of the project.
    operator : str
        Person responsible for running the analysis.
    date : str
        Date of the experiment in DD/MM/YYYY format.

    [inputs]
    commands : str or list
        Commands to execute. Can be a Python expression string (e.g.,
        "sleep {k}") or a list of commands.
    parameters : str
        Additional parameters passed to the container execution command
        (e.g., "--cleanenv").

    [environment]
    cluster : str
        Cluster type (e.g., "pbs").
    folder : str
        Working directory for job execution (e.g., "/tmp/hopla").
    queue : str
        Queue or partition name (e.g., "Nspin_short").
    walltime : int
        Maximum walltime in hours for each job.
    n_cpus : int
        Number of CPUs allocated per job.
    image : str
        Path to container image used for execution.

    [config]
    dryrun : bool
        If true, simulate job submission without executing.
    delay_s : int
        Delay in seconds between submissions.
    verbose : bool
        If true, enable verbose logging.

    Examples
    --------
    >>> hoplactl --config experiment.toml --njobs 5 # doctest: +SKIP

    Notes
    -----
    - The `multi` section should define `n_splits` to control chunking.
    - The `Config` context manager is used to apply configuration settings
      during execution.

    Raises
    ------
    ValueError
        If 'data.tsv' is missing.
    """
    print_header()

    parser = argparse.ArgumentParser(
        prog="hoplactl",
        description=(
            "Automate job execution with hopla using a configuration file.\n\n"
            "This function parses command-line arguments, loads a TOML "
            "configuration file, initializes a hopla executor, and submits "
            "jobs either individually or in chunks depending on the "
            "configuration. It then runs the executor with a specified "
            "maximum number of jobs and writes a report to disk."
        ),
        epilog=(
            "Notes:\n- Use a valid TOML file.\n- Add a 'data.tsv' file next "
            "to the configuration file if needed.\n- See docs for examples."
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--config",
        type=str,
        required=True,
        help=(
            "Path to an experiment TOML configuration file. The file must "
            "contain sections for `project`, `environment`, `inputs`, and "
            "`config`. Optionally, a `multi` section can be provided to split "
            "commands into chunks."
        )
    )
    parser.add_argument(
        "--njobs",
        type=int,
        required=True,
        help="The maximum number of job submissions to execute concurrently."
    )
    parser.add_argument(
        "--venv",
        action="store_true",
        help=(
            "Enable this option to run the command outside of a container. "
            "In this case, the image environment parameter is automatically "
            "set to None, so providing it is optional."
        )
    )
    args = parser.parse_args()

    with open(args.config, "rb") as of:
        config = tomllib.load(of)
    print_toml(config)

    if args.venv:
        config["environment"]["image"] = ""
    executor = hopla.Executor(
        **config["environment"]
    )
    if args.venv:
        executor._job_class._container_cmd = "{command}"

    commands = config["inputs"]["commands"]
    if not isinstance(commands, (list, tuple)):
        data_file = Path(args.config).parent / "data.tsv"
        if not data_file.is_file():
            raise ValueError(
                "A TSV file named 'data.tsv' must be located next to the "
                "configuration file. It is needed to fill the 'commands' "
                "Python expression string in TOML configuration. Column "
                "names must match expression keys."
            )
        df = pd.read_csv(data_file, sep="\t")
        commands = [
            shlex.split(commands.format(**dict(row))) for _, row in df.iterrows()
        ]

    if config.get("multi") is not None:
        chunks = np.array_split(commands, config["multi"]["n_splits"])
        _ = [
            executor.submit(
                [hopla.DelayedSubmission(*cmd) for cmd in subcmds],
                execution_parameters=config["inputs"].get("parameters"),
            ) for subcmds in chunks
        ]
    else:
        _ = [
            executor.submit(
                *cmd,
                execution_parameters=config["inputs"].get("parameters"),
            ) for cmd in commands
        ]

    with Config(**config["config"]):
        executor(max_jobs=args.njobs)

    report_file = executor.folder / "report.txt"
    with open(report_file, "w") as of:
        of.write(executor.report)


if __name__ == "__main__":
    main()
