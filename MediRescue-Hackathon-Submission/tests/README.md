# MediRescue automated tests

The suite uses Python's standard `unittest` library and Flask's test client. It uses a temporary SQLite database and mocks AWS notification/mirroring functions, so tests do not send real notifications or require AWS credentials.

Run from the project directory after installing `requirements.txt`:

```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

The tests cover the core local emergency lifecycle, including safety-window cancellation, idempotent confirmation, hospital acceptance protection, driver state validation, completion/availability, timeline events, and GPS validation.
