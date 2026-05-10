BEGIN;

UPDATE tc_devices
SET positionid = NULL,
    lastupdate = NULL;

TRUNCATE TABLE tc_positions RESTART IDENTITY CASCADE;
TRUNCATE TABLE tc_events RESTART IDENTITY CASCADE;
TRUNCATE TABLE tc_statistics RESTART IDENTITY CASCADE;

COMMIT;

SELECT 'cleanup_done' AS status;


select * from tc_positions;



BEGIN;

-- Reset current device pointers
UPDATE tc_devices
SET positionid = NULL,
    lastupdate = NULL;

-- Clear runtime telemetry/history
TRUNCATE TABLE tc_positions RESTART IDENTITY CASCADE;
TRUNCATE TABLE tc_events RESTART IDENTITY CASCADE;
TRUNCATE TABLE tc_statistics RESTART IDENTITY CASCADE;

COMMIT;

SELECT 'fresh_test_ready' AS status;