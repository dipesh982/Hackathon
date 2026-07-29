-- Identify unused tables and generate Cortex-powered cleanup recommendations
--Step 1: Identify Unused Tables

CREATE OR REPLACE TABLE UNUSED_TABLES AS
SELECT 
t.TABLE_SCHEMA,
t.TABLE_NAME,
t.LAST_ALTERED,
t.ROW_COUNT
FROM INFORMATION_SCHEMA.TABLES t
WHERE t.TABLE_TYPE = 'BASE TABLE'
AND CONCAT(CURRENT_DATABASE(), '.', t.TABLE_SCHEMA, '.', t.TABLE_NAME) NOT IN (
    SELECT DISTINCT f.VALUE:objectName::STRING
    FROM SNOWFLAKE.ACCOUNT_USAGE.ACCESS_HISTORY,
    LATERAL FLATTEN(input => BASE_OBJECTS_ACCESSED) f
    WHERE QUERY_START_TIME >= DATEADD(DAY, -90, CURRENT_TIMESTAMP())
    AND f.VALUE:objectDomain::STRING = 'Table'
);

--Step 2: Cortex Recommendation

CREATE OR REPLACE TABLE CLEANUP_RECOMMENDATIONS AS
SELECT 
TABLE_SCHEMA,
TABLE_NAME,
SNOWFLAKE.CORTEX.COMPLETE(
'mistral-large',
CONCAT(
'You are a data governance expert.
Table ', TABLE_NAME, ' in schema ', TABLE_SCHEMA,
' has not been accessed in 90 days.
Suggest:
1. Archive strategy
2. Drop recommendation
3. Risk level'
)
) AS RECOMMENDATION
FROM UNUSED_TABLES;

--Step 3: Tagging for Governance (apply per table from UNUSED_TABLES)

-- Example: ALTER TABLE MY_SCHEMA.MY_TABLE SET TAG retention = 'candidate_for_cleanup';

--Automation Layer (Critical)
--Use Snowflake Tasks

CREATE OR REPLACE TASK DAILY_OPTIMIZATION_TASK
WAREHOUSE = COMPUTE_WH
SCHEDULE = 'USING CRON 0 2 * * * UTC'
AS
CALL RUN_GENAI_OPTIMIZATION();

--Stored Procedure Wrapper

CREATE OR REPLACE PROCEDURE RUN_GENAI_OPTIMIZATION()
RETURNS STRING
LANGUAGE SQL
AS
$$
BEGIN
    -- Identify Unused Tables
    -- Run Cortex optimization
    -- Tag for Governance
    RETURN 'Done';
END;
$$;
