# Course History paste fixtures

Each fixture is a pair of files:

- `<name>.txt`: text pasted from SIS → Academic Record → Course History (Ctrl+A, Ctrl+C).
- `<name>.expected.json`: the rows the parser must find, as a list of
  `{"code", "term", "grade", "status"}` objects.

`test_history.py` checks every pair. The F11.3 acceptance criterion is 10
students' pastes parsing correctly. Add real pastes only with the student's
permission and after you anonymise them:

- remove the student's name, ID, email and any header showing them;
- keep only the menu text and the course table.

Never commit a paste that could identify a student.
