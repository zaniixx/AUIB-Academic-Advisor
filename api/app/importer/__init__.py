"""The course catalog and program packages: loading, validating and importing them (F0.1, F0.6, F0.7).

The course catalog, ``data/catalog/courses.json``, holds every AUIB course in the SIS
scraper's format and is shared by all programs. A program package is a folder under
``data/programs/<program-id>/`` with:

* ``program.json``: name, kind (major or minor), catalog year, source and date,
  readable labels and roles for the requirement groups, and whether it is published;
* ``requirements.json``: the requirement tree in the SIS scraper's format.

Adding a program is adding a package and running ``python -m app.cli import``;
no code changes are needed.
"""
