-- Drinking water pipeline, step 0: raw volume and helpers.
-- Runs in the personal schema users.suresh_kandru (no catalog rights needed);\n-- layers are table-name prefixes: bronze_*, silver_*, and unprefixed v_* views.\n-- Medallion layers: bronze (raw strings) -> silver (typed, cleaned)
-- -> gold (the v_* views the MCP server reads).
--
-- Upload the raw files to the volume before running 01_bronze.sql:
--   /Volumes/users/suresh_kandru/raw/drinking_water/current/
--     pws_systems.csv
--     safer_risk_assessment.csv
--     lead_schools.csv
--     ddw_source_chemistry_2020_present.csv
--     zcta_centroids.txt   (US Census Gazetteer ZCTA file, tab-delimited:
--                           https://www.census.gov/geographies/reference-files/time-series/geo/gazetteer-files.html)
-- Files come from scripts/download_drinking_water_data.py (data.ca.gov).

CREATE VOLUME IF NOT EXISTS users.suresh_kandru.raw;

-- Source files use several spellings for "no value".
CREATE OR REPLACE FUNCTION users.suresh_kandru.silver_clean_str(x STRING)
  RETURNS STRING
  COMMENT 'Trim; map empty/NULL/NaN/N/A/NA placeholders to SQL NULL.'
  RETURN CASE
    WHEN upper(trim(x)) IN ('', 'NULL', 'NAN', 'N/A', 'NA') THEN NULL
    ELSE trim(x)
  END;
