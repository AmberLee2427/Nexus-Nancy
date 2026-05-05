Nexus-Nancy
===========

Nexus-Nancy is a lightweight, pip-installable agent TUI designed for Nexus-style environments: clusters, shared computing, and SSH-accessed environments. It runs without admin privileges, assuming Python is available.

.. toctree::
   :maxdepth: 2
   :caption: Getting Started

   Installation <self>
   Models & Authentication <MODELS_AND_AUTH>
   Extending: Plugins & Tools <PLUGINS>

Quick start
-----------

.. code-block:: bash

   pip install nexus-nancy
   nnancy

Or for development:

.. code-block:: bash

   pip install -e .
   nnancy

Core commands
-------------

- ``nnancy`` - Start interactive TUI mode
- ``nnancy -t "..."`` - One-shot prompt mode
- ``nnancy doctor`` - Verify installation and configuration
- ``nnancy config`` - Edit ``.agents/nnancy.yaml`` in your editor
- ``nnancy instructions`` - Edit ``.agents/instructions.txt`` in your editor
- ``nnancy secrets`` - Edit API keys in your editor
- ``nnancy auth login`` - Login via OAuth (Codex)

In-session slash commands
-------------------------

- ``/new`` - Start a fresh in-process context
- ``/handoff`` - Save a handoff snapshot
- ``/handoff PATH`` - Load a prior handoff snapshot
- ``/config`` - Open ``.agents/nnancy.yaml`` in your editor
- ``/key NEW_API_KEY`` - Replace the API key file value

For TUI sessions, ``/key`` without an argument opens hidden input prompts (value + confirmation) and does not print the key value.

Runtime files
-------------

On first run in a directory, Nexus-Nancy creates local agent files:

- ``.agents/instructions.txt`` - System prompt for the agent
- ``.agents/nnancy.yaml`` - Configuration (model, auth, etc.)
- ``.agents/relay_instructions.txt`` - Handoff relay prompt
- ``.agents/hand-off_instructions.txt`` - Handoff summary prompt
- ``.agents/sandbox_allowlist.txt`` - Allowed command substrings
- ``.agents/secrets/openai.key`` - API key storage (created when setting a key)

These are directory-local so each project can have its own behavior.

Design philosophy
-----------------

- **Minimalist Configuration**: No commands to switch models. Edit ``.agents/nnancy.yaml`` directly to ensure the config file is always the source of truth.
- **Admin-Free**: Runs without root or sudo privileges, assuming Python is available.
- **Extensible**: Two pathways for adding tools - pip-installable plugins or drop-in local scripts.

License
-------

MIT