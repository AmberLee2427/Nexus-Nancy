Nexus-Nancy
===========

Nexus-Nancy is a lightweight, pip-installable agent TUI for Nexus-style environments.

Quick start
-----------

.. code-block:: bash

   pip install -e .
   nnancy

Core commands
-------------

- ``nnancy``: interactive mode
- ``nnancy -t \"prompt\"``: one-shot prompt mode
- ``nnancy instructions``: edit workspace instructions in your editor
- ``nnancy config``: edit workspace YAML config in your editor

Runtime files
-------------

On first run in a directory, Nexus-Nancy creates local agent files:

- ``.agents/instructions.txt``
- ``.agents/nnancy.yaml``

These are directory-local so each project can have its own behavior.
