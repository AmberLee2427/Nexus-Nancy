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

In-session slash commands
-------------------------

- ``/new``: start a fresh in-process context
- ``/handoff``: save a handoff snapshot
- ``/handoff PATH``: load a prior handoff snapshot
- ``/config``: open ``.agents/nnancy.yaml`` in your editor
- ``/key NEW_API_KEY``: replace the API key file value

For TUI sessions, ``/key`` without an argument opens hidden input prompts (value + confirmation) and does not print the key value.

Runtime files
-------------

On first run in a directory, Nexus-Nancy creates local agent files:

- ``.agents/instructions.txt``
- ``.agents/nnancy.yaml``
- ``.agents/secrets/openai.key`` (created when setting a key)

These are directory-local so each project can have its own behavior.
