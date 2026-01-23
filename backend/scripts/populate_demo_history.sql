-- =============================================================================
-- Populate Demo Account Test History (TASK-506)
-- =============================================================================
-- This script creates representative test history for the App Store demo account.
-- Run this via: railway connect postgres < scripts/populate_demo_history.sql
--
-- IMPORTANT: This must be run AFTER creating the demo user via API.
-- The script looks up the user by email: demo-reviewer@aiq-app.com
-- =============================================================================

-- Verify the demo user exists
DO $$
DECLARE
    demo_user_id INTEGER;
    demo_email TEXT := 'demo-reviewer@aiq-app.com';
BEGIN
    -- Get the demo user ID
    SELECT id INTO demo_user_id FROM users WHERE email = demo_email;

    IF demo_user_id IS NULL THEN
        RAISE EXCEPTION 'Demo user not found. Please create the demo account via API first.';
    END IF;

    RAISE NOTICE 'Found demo user with ID: %', demo_user_id;

    -- Check if test history already exists
    IF EXISTS (SELECT 1 FROM test_results WHERE user_id = demo_user_id) THEN
        RAISE NOTICE 'Test history already exists for demo user. Skipping.';
        RETURN;
    END IF;

    RAISE NOTICE 'Creating test history for demo user...';
END $$;

-- Create Test Session 1 (8 months ago, IQ: 112)
INSERT INTO test_sessions (user_id, status, started_at, completed_at, composition_metadata)
SELECT
    u.id,
    'COMPLETED',
    NOW() - INTERVAL '240 days',
    NOW() - INTERVAL '240 days' + INTERVAL '20 minutes',
    '{"strategy": "demo_account", "marker": "APP_STORE_REVIEW_DEMO"}'::jsonb
FROM users u
WHERE u.email = 'demo-reviewer@aiq-app.com'
AND NOT EXISTS (SELECT 1 FROM test_results WHERE user_id = u.id);

-- Create Test Result 1
INSERT INTO test_results (
    test_session_id, user_id, iq_score, percentile_rank,
    total_questions, correct_answers, completion_time_seconds,
    completed_at, standard_error, ci_lower, ci_upper, validity_status
)
SELECT
    ts.id,
    ts.user_id,
    112,
    79.0,
    20,
    13,
    1200,
    ts.completed_at,
    4.5,
    103,
    121,
    'valid'
FROM test_sessions ts
JOIN users u ON ts.user_id = u.id
WHERE u.email = 'demo-reviewer@aiq-app.com'
AND ts.started_at < NOW() - INTERVAL '200 days'
AND NOT EXISTS (
    SELECT 1 FROM test_results tr WHERE tr.test_session_id = ts.id
);

-- Create Test Session 2 (2 months ago, IQ: 115)
INSERT INTO test_sessions (user_id, status, started_at, completed_at, composition_metadata)
SELECT
    u.id,
    'COMPLETED',
    NOW() - INTERVAL '60 days',
    NOW() - INTERVAL '60 days' + INTERVAL '18 minutes',
    '{"strategy": "demo_account", "marker": "APP_STORE_REVIEW_DEMO"}'::jsonb
FROM users u
WHERE u.email = 'demo-reviewer@aiq-app.com'
AND NOT EXISTS (SELECT 1 FROM test_sessions WHERE user_id = u.id AND started_at > NOW() - INTERVAL '100 days');

-- Create Test Result 2
INSERT INTO test_results (
    test_session_id, user_id, iq_score, percentile_rank,
    total_questions, correct_answers, completion_time_seconds,
    completed_at, standard_error, ci_lower, ci_upper, validity_status
)
SELECT
    ts.id,
    ts.user_id,
    115,
    84.0,
    20,
    14,
    1080,
    ts.completed_at,
    4.5,
    106,
    124,
    'valid'
FROM test_sessions ts
JOIN users u ON ts.user_id = u.id
WHERE u.email = 'demo-reviewer@aiq-app.com'
AND ts.started_at > NOW() - INTERVAL '100 days'
AND NOT EXISTS (
    SELECT 1 FROM test_results tr WHERE tr.test_session_id = ts.id
);

-- Verify the results
SELECT
    'Test History Created' as status,
    COUNT(*) as total_results,
    MIN(tr.completed_at)::date as oldest_test,
    MAX(tr.completed_at)::date as newest_test,
    ARRAY_AGG(tr.iq_score ORDER BY tr.completed_at) as scores
FROM test_results tr
JOIN users u ON tr.user_id = u.id
WHERE u.email = 'demo-reviewer@aiq-app.com';
