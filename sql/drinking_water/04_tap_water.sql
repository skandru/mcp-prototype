-- Tap-water results by ZIP: Bronze -> Silver -> Gold in one file.
-- Run after 00_setup.sql..03_gold.sql. Needs two extra files in the volume
-- /Volumes/users/suresh_kandru/raw/drinking_water/current/ :
--   tap_water_results.csv.gz  (scripts/build_tap_water_results.py; DDW SDWIS
--                              sample results, distribution/treated points)
--   zip_service_areas.csv     (scripts/build_zip_service_areas.py; ZIP polygon
--                              x water-system service-area polygon overlap)

-- ---------------------------------------------------------------- Bronze
CREATE OR REPLACE TABLE users.suresh_kandru.bronze_dw_tap_results AS
SELECT
  *,
  _metadata.file_path AS _source_file,
  current_timestamp() AS _ingested_at
FROM read_files(
  '/Volumes/users/suresh_kandru/raw/drinking_water/current/tap_water_results.csv.gz',
  format => 'csv', header => true, inferSchema => false,
  schema => 'pws_id STRING, system_name STRING, ps_code STRING, sampling_point STRING, facility_type STRING, sample_type STRING, sample_date STRING, analyte_code STRING, analyte_name STRING, result STRING, units STRING, less_than_rl STRING, reporting_level STRING, dlr STRING, mcl STRING, method STRING'
);

CREATE OR REPLACE TABLE users.suresh_kandru.bronze_dw_zip_service_areas AS
SELECT
  *,
  _metadata.file_path AS _source_file,
  current_timestamp() AS _ingested_at
FROM read_files(
  '/Volumes/users/suresh_kandru/raw/drinking_water/current/zip_service_areas.csv',
  format => 'csv', header => true, inferSchema => false,
  schema => 'zip STRING, pws_id STRING, system_name STRING, overlap_sq_km STRING, pct_of_zip_covered STRING, pct_of_system_in_zip STRING'
);

-- ---------------------------------------------------------------- Silver
-- Typed results. A "<" result (less_than_rl = 'Y') is a non-detect: the
-- numeric result is NULL and reporting_limit says how low the lab could see.
CREATE OR REPLACE TABLE users.suresh_kandru.silver_dw_tap_results AS
WITH t AS (
  SELECT
    upper(trim(pws_id)) AS pws_id,
    users.suresh_kandru.silver_clean_str(ps_code) AS sampling_point_id,
    users.suresh_kandru.silver_clean_str(sampling_point) AS sampling_point,
    upper(trim(facility_type)) AS facility_type,
    users.suresh_kandru.silver_clean_str(sample_type) AS sample_type,
    try_cast(sample_date AS DATE) AS sample_date,
    initcap(users.suresh_kandru.silver_clean_str(analyte_name)) AS analyte_name,
    users.suresh_kandru.silver_clean_str(analyte_code) AS analyte_code,
    try_cast(users.suresh_kandru.silver_clean_str(result) AS DOUBLE) AS result_numeric,
    upper(users.suresh_kandru.silver_clean_str(units)) AS units,
    upper(trim(less_than_rl)) = 'Y' AS is_non_detect,
    try_cast(users.suresh_kandru.silver_clean_str(reporting_level) AS DOUBLE) AS reporting_limit,
    try_cast(users.suresh_kandru.silver_clean_str(mcl) AS DOUBLE) AS mcl,
    users.suresh_kandru.silver_clean_str(method) AS method
  FROM users.suresh_kandru.bronze_dw_tap_results
)
SELECT
  *,
  CASE facility_type
    WHEN 'DS' THEN 'distribution'
    WHEN 'TP' THEN 'treated'
    WHEN 'CW' THEN 'treated'
    ELSE 'other'
  END AS water_stage,
  (NOT is_non_detect AND result_numeric IS NOT NULL AND mcl IS NOT NULL
    AND mcl > 0 AND result_numeric > mcl) AS exceeds_mcl
FROM t
WHERE pws_id RLIKE '^CA[0-9]{7}$' AND sample_date IS NOT NULL
  AND analyte_name IS NOT NULL;

-- Latest sample per system, stage and analyte, plus period context.
CREATE OR REPLACE TABLE users.suresh_kandru.silver_dw_tap_latest AS
WITH ranked AS (
  SELECT
    *,
    row_number() OVER (
      PARTITION BY pws_id, water_stage, analyte_name
      ORDER BY sample_date DESC, result_numeric DESC NULLS LAST
    ) AS rn,
    count(*) OVER (PARTITION BY pws_id, water_stage, analyte_name) AS sample_count,
    max(result_numeric) OVER (PARTITION BY pws_id, water_stage, analyte_name) AS max_result_numeric,
    max(exceeds_mcl) OVER (PARTITION BY pws_id, water_stage, analyte_name) AS any_exceeds_mcl
  FROM users.suresh_kandru.silver_dw_tap_results
)
SELECT
  pws_id, water_stage, analyte_name, analyte_code, sampling_point,
  sample_date, result_numeric, units, is_non_detect, reporting_limit, mcl,
  exceeds_mcl, method, sample_count, max_result_numeric, any_exceeds_mcl
FROM ranked
WHERE rn = 1;

-- ZIP -> system lookup; drop slivers where a system covers <1% of the ZIP.
CREATE OR REPLACE TABLE users.suresh_kandru.silver_dw_zip_service_areas AS
SELECT
  lpad(trim(zip), 5, '0') AS zip,
  upper(trim(pws_id)) AS pws_id,
  try_cast(overlap_sq_km AS DOUBLE) AS overlap_sq_km,
  try_cast(pct_of_zip_covered AS DOUBLE) AS pct_of_zip_covered,
  try_cast(pct_of_system_in_zip AS DOUBLE) AS pct_of_system_in_zip
FROM users.suresh_kandru.bronze_dw_zip_service_areas
WHERE try_cast(pct_of_zip_covered AS DOUBLE) >= 1;

-- ---------------------------------------------------------------- Gold
CREATE OR REPLACE VIEW users.suresh_kandru.v_tap_water_for_zip
COMMENT 'Latest drinking-water sample results (DDW SDWIS, 2023-present) for every water system whose service area overlaps a ZIP code. One row per zip, system, water_stage and analyte. System-level samples, not per-address results; not a health determination.'
AS
SELECT
  z.zip,
  z.pct_of_zip_covered,
  r.pws_id,
  s.system_name,
  s.total_population,
  r.water_stage,
  r.analyte_name,
  r.result_numeric,
  r.units,
  r.is_non_detect,
  r.reporting_limit,
  r.mcl,
  r.exceeds_mcl,
  r.any_exceeds_mcl,
  r.max_result_numeric,
  r.sample_count,
  r.sample_date AS last_observed,
  r.sampling_point,
  r.method,
  'https://www.waterboards.ca.gov/drinking_water/certlic/drinkingwater/EDTlibrary.html' AS source_url
FROM users.suresh_kandru.silver_dw_zip_service_areas z
JOIN users.suresh_kandru.silver_dw_tap_latest r USING (pws_id)
LEFT JOIN users.suresh_kandru.silver_dw_systems s USING (pws_id);
