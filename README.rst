**Usage**

.. image:: https://img.shields.io/badge/python-3.12-blue
    :target: https://github.com/AGrigis/pysphinxdoc
    :alt: Python Version

.. image:: https://img.shields.io/badge/License-CeCILL--B-blue.svg
    :target: http://www.cecill.info/licences/Licence_CeCILL-B_V1-en.html
    :alt: License

.. image:: https://img.shields.io/badge/Powered%20by-CEA%2FNeuroSpin-blue.svg
    :target: https://joliot.cea.fr/drf/joliot/Pages/Entites_de_recherche/NeuroSpin.aspx
    :alt: Powered By

**Development**

.. image:: https://coveralls.io/repos/github/brainprepdesk/hopla/badge.svg
    :target: https://coveralls.io/github/brainprepdesk/hopla
    :alt: Code Coverage

.. image:: https://github.com/brainprepdesk/hopla/actions/workflows/pycodestyle.yml/badge.svg
    :target: https://github.com/brainprepdesk/hopla/actions
    :alt: Github Actions PyCodeStyle Linter Status

.. image:: https://github.com/brainprepdesk/hopla/actions/workflows/ruff.yml/badge.svg
    :target: https://github.com/brainprepdesk/hopla/actions
    :alt: Github Actions Ruff Linter Status

.. image:: https://github.com/brainprepdesk/hopla/actions/workflows/testing.yml/badge.svg
    :target: https://github.com/brainprepdesk/hopla/actions
    :alt: Github Actions Testing Status

.. image:: https://github.com/brainprepdesk/hopla/actions/workflows/documentation.yml/badge.svg
    :target: https://github.com/brainprepdesk/hopla/actions
    :alt: Github Actions Documentation Build Status

**Release**

.. image:: https://badge.fury.io/py/hopla.svg
    :target: https://badge.fury.io/py/hopla
    :alt: Pypi Package



Hopla!
======

What Is Hopla?
==============

Hopla is a lightweight tool for submitting script for computation within
different clusters. It basically wraps submission and provide access to logs.


Important Links
===============

- Official source code repo: https://github.com/brainprepdesk/hopla
- HTML documentation (stable release): http://brainprepdesk.github.io/hopla/stable
- HTML documentation (dev): http://brainprepdesk.github.io/hopla/dev


Install
=======

Latest release
--------------

**1. Setup a virtual environment**

We recommend that you install ``hopla`` in a virtual Python environment,
either managed with the standard library ``venv`` or with ``conda``.
Either way, create and activate a new python environment.

With ``venv``:

.. code-block:: bash

    python3 -m venv /<path_to_new_env>
    source /<path_to_new_env>/bin/activate

Windows users should change the last line to ``\<path_to_new_env>\Scripts\activate.bat``
in order to activate their virtual environment.

With ``conda``:

.. code-block:: bash

    conda create -n hopla python=3.12
    conda activate hopla

**2. Install hopla with pip**

Execute the following command in the command prompt / terminal
in the proper python environment:

.. code-block:: bash

    python3 -m pip install -U hopla


Check installation
------------------

Try importing hopla in a python / iPython session:

.. code-block:: python

    import hopla

If no error is raised, you have installed hopla correctly.


Dependencies
============

The required dependencies to use the software are listed
in the file `pyproject.toml <https://github.com/brainprepdesk/hopla/blob/master/pyproject.toml>`_.
