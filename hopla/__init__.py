##########################################################################
# Hopla - Copyright (C) AGrigis, 2025
# Distributed under the terms of the CeCILL-B license, as published by
# the CEA-CNRS-INRIA. Refer to the LICENSE file or to
# http://www.cecill.info/licences/Licence_CeCILL-B_V1-en.html
# for details.
##########################################################################

"""
``hopla`` can automate job creation, submission, monitoring, and resubmission,
saving hours of repetitive work. When you're running hundreds or thousands of
jobs automating code execution on clusters is convenient, but also essential
for scalability, and efficiency.
"""

__version__ = "2.1.0"
from .executor import DelayedSubmission, Executor
