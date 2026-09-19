# MediRescue V12 – Test Plan

## Automated suite

Run:

`python -m unittest discover -s tests -p "test_*.py" -v`

The suite is intentionally local. AWS functions are mocked and a temporary SQLite database is used.

## Manual end-to-end smoke test

1. Start the app.
2. Patient: Detect My Location and verify coordinates.
3. Patient: Send SOS and cancel within 5 seconds. Confirm no hospital alert appears.
4. Repeat SOS and let the timer finish.
5. Hospital: accept the emergency.
6. Driver: accept and start GPS.
7. Driver: mark Picked Up.
8. Driver: Complete Trip.
9. Patient: verify final status is COMPLETED and timeline contains the lifecycle events.
10. Hospital: verify driver/ambulance details and released capacity.

## Expected state sequence

`PENDING_CONFIRMATION → HOSPITAL_BROADCAST → HOSPITAL_ACCEPTED → DISPATCHED → PICKED_UP → COMPLETED`

Cancellation is valid only from `PENDING_CONFIRMATION`. Invalid transitions should return an HTTP 4xx response and must not change the emergency state.
