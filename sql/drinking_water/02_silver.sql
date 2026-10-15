-- Silver: typed, cleaned, deduplicated tables. Placeholders become NULL,
-- dates become DATE, non-detects are explicit (never cast "<" blindly).

-- ZIP centroids restricted to a California bounding box (includes a few border
-- ZIPs); used to turn lat/lon points into zip + distance_km pairs.
CREATE OR REPLACE TABLE users.suresh_kandru.silver_zip_centroids AS
SELECT
  lpad(trim(geoid), 5, '0') AS zip,
  try_cast(trim(intptlat) AS DOUBLE) AS latitude,
  try_cast(trim(intptlong) AS DOUBLE) AS longitude
FROM users.suresh_kandru.bronze_zcta_centroids
WHERE try_cast(trim(intptlat) AS DOUBLE) BETWEEN 32.0 AND 42.5
  AND try_cast(trim(intptlong) AS DOUBLE) BETWEEN -125.0 AND -114.0;

-- One row per public water system (SDWIS inventory).
CREATE OR REPLACE TABLE users.suresh_kandru.silver_dw_systems AS
SELECT
  upper(trim(water_system_no)) AS pws_id,
  users.suresh_kandru.silver_clean_str(water_system_name) AS system_name,
  users.suresh_kandru.silver_clean_str(principal_county_served) AS county,
  users.suresh_kandru.silver_clean_str(city) AS city,
  users.suresh_kandru.silver_clean_str(federal_system_type_code) AS federal_type_code,
  users.suresh_kandru.silver_clean_str(federal_system_type) AS federal_type,
  users.suresh_kandru.silver_clean_str(state_system_type) AS state_type,
  users.suresh_kandru.silver_clean_str(system_status) AS status,
  users.suresh_kandru.silver_clean_str(owner_type) AS owner_type,
  users.suresh_kandru.silver_clean_str(primary_source_type) AS primary_source_type,
  try_cast(users.suresh_kandru.silver_clean_str(residential_population) AS INT) AS residential_population,
  try_cast(users.suresh_kandru.silver_clean_str(total_population) AS INT) AS total_population,
  try_cast(users.suresh_kandru.silver_clean_str(total_service_connections) AS INT) AS service_connections,
  try_to_date(users.suresh_kandru.silver_clean_str(sanitary_survey_date), 'M/d/yyyy') AS last_sanitary_survey,
  to_date(_ingested_at) AS data_as_of
FROM users.suresh_kandru.bronze_dw_pws_systems
WHERE users.suresh_kandru.silver_clean_str(water_system_no) IS NOT NULL
QUALIFY row_number() OVER (
  PARTITION BY upper(trim(water_system_no)) ORDER BY _ingested_at DESC
) = 1;

-- SAFER risk assessment: one row per system, with coordinates. Only the
-- columns the Gold views expose; the full detail stays in Bronze.
CREATE OR REPLACE TABLE users.suresh_kandru.silver_dw_safer AS
SELECT
  upper(trim(WATER_SYSTEM_NUMBER)) AS pws_id,
  try_cast(users.suresh_kandru.silver_clean_str(LATITUDE_MEASURE) AS DOUBLE) AS latitude,
  try_cast(users.suresh_kandru.silver_clean_str(LONGITUDE_MEASURE) AS DOUBLE) AS longitude,
  users.suresh_kandru.silver_clean_str(FINAL_SAFER_STATUS) AS safer_status,
  users.suresh_kandru.silver_clean_str(RISK_ASSESSMENT_RESULT) AS risk_assessment_result,
  upper(trim(CURRENT_FAILING)) = 'FAILING' AS is_failing,
  try_to_date(users.suresh_kandru.silver_clean_str(FAILING_START_DATE), 'yyyy-MM-dd') AS failing_start_date,
  users.suresh_kandru.silver_clean_str(SERVICE_AREA_ECONOMIC_STATUS) AS economic_status,
  try_cast(regexp_replace(users.suresh_kandru.silver_clean_str(MHI), '[$,]', '') AS INT) AS median_household_income,
  try_cast(users.suresh_kandru.silver_clean_str(CALENVIRO_SCREEN_SCORE) AS DOUBLE) AS calenviroscreen_score,
  upper(trim(PRIMARY_MCL_VIOLATION)) = 'YES' AS has_primary_mcl_violation,
  users.suresh_kandru.silver_clean_str(PRIMARY_ANALYTES) AS primary_mcl_analytes,
  upper(trim(SECONDARY_MCL_VIOLATION)) = 'YES' AS has_secondary_mcl_violation,
  users.suresh_kandru.silver_clean_str(SECONDARY_ANALYTES) AS secondary_mcl_analytes,
  upper(trim(E_COLI_VIOLATION)) = 'YES' AS has_ecoli_violation,
  users.suresh_kandru.silver_clean_str(E_COLI_ANALYTES) AS ecoli_analytes,
  upper(trim(TREATMENT_TECHNIQUE_VIOLATION)) = 'YES' AS has_treatment_technique_violation,
  users.suresh_kandru.silver_clean_str(TT_ANALYTES) AS treatment_technique_analytes,
  upper(trim(MONITORING_AND_REPORTING_VIOLATION)) = 'YES' AS has_monitoring_violation,
  users.suresh_kandru.silver_clean_str(MONITORING_AND_REPORTING_ANALYTES) AS monitoring_violation_analytes,
  users.suresh_kandru.silver_clean_str(WATER_QUALITY_RISK_LEVEL) AS water_quality_risk_level,
  users.suresh_kandru.silver_clean_str(ASSESSIBILITY_RISK_LEVEL) AS accessibility_risk_level,
  users.suresh_kandru.silver_clean_str(AFFORDABILITY_RISK_LEVEL) AS affordability_risk_level,
  users.suresh_kandru.silver_clean_str(TMF_CAPACITY_RISK_LEVEL) AS tmf_capacity_risk_level,
  try_cast(users.suresh_kandru.silver_clean_str(TOTAL_WEIGHTED_RISK_SCORE_BEFORE_DIVIDING_BY_CATEGORY_COUNT) AS DOUBLE) AS total_weighted_risk_score,
  to_date(_ingested_at) AS data_as_of
FROM users.suresh_kandru.bronze_dw_safer_risk_assessment
WHERE users.suresh_kandru.silver_clean_str(WATER_SYSTEM_NUMBER) IS NOT NULL
QUALIFY row_number() OVER (
  PARTITION BY upper(trim(WATER_SYSTEM_NUMBER)) ORDER BY _ingested_at DESC
) = 1;

-- Lead sampling at K-12 schools. Street addresses are dropped; only the ZIP is
-- kept (parsed from the end of school_address) so Gold carries no address PII.
CREATE OR REPLACE TABLE users.suresh_kandru.silver_dw_lead_schools AS
SELECT DISTINCT
  upper(trim(pws_id)) AS pws_id,
  users.suresh_kandru.silver_clean_str(pscode) AS sample_site_code,
  users.suresh_kandru.silver_clean_str(district) AS district,
  users.suresh_kandru.silver_clean_str(school_name) AS school_name,
  users.suresh_kandru.silver_clean_str(school_site_name) AS sample_location,
  nullif(regexp_extract(school_address, r'(\d{5})(-\d{4})?\s*$', 1), '') AS zip,
  users.suresh_kandru.silver_clean_str(school_county) AS school_county,
  users.suresh_kandru.silver_clean_str(school_type) AS school_type,
  users.suresh_kandru.silver_clean_str(water_system_name) AS water_system_name,
  coalesce(try_to_date(sample_date, 'yyyy-MM-dd'), try_to_date(samp_date, 'yyyyMMdd')) AS sample_date,
  trim(xmod) = '<' AS is_non_detect,
  if(trim(xmod) = '<', NULL, try_cast(users.suresh_kandru.silver_clean_str(result) AS DOUBLE)) AS result_numeric,
  if(trim(xmod) = '<', try_cast(users.suresh_kandru.silver_clean_str(result) AS DOUBLE), NULL) AS reporting_limit,
  users.suresh_kandru.silver_clean_str(rpt_unit) AS units,
  lower(trim(action_level_exceedance)) = 'yes' AS action_level_exceeded,
  users.suresh_kandru.silver_clean_str(ale_follow_up_action) AS follow_up_action,
  users.suresh_kandru.silver_clean_str(ale_follow_up_status) AS follow_up_status
FROM users.suresh_kandru.bronze_dw_lead_schools
WHERE users.suresh_kandru.silver_clean_str(pws_id) IS NOT NULL;

-- DDW/GAMA source (well) chemistry, 2020-present. The well id is
-- "<pws_id>_<source>_<source>", so the owning system is its first segment.
CREATE OR REPLACE TABLE users.suresh_kandru.silver_dw_source_chemistry AS
SELECT DISTINCT
  trim(gm_well_id) AS well_id,
  split(trim(gm_well_id), '_')[0] AS pws_id,
  users.suresh_kandru.silver_clean_str(gm_county_name) AS county,
  users.suresh_kandru.silver_clean_str(src_well_category) AS well_category,
  users.suresh_kandru.silver_clean_str(gm_chemical_vvl) AS chemical_code,
  users.suresh_kandru.silver_clean_str(gm_chemical_name) AS chemical_name,
  users.suresh_kandru.silver_clean_str(gm_cas_number) AS cas_number,
  trim(gm_result_modifier) = '<' AS is_non_detect,
  if(trim(gm_result_modifier) = '<', NULL, try_cast(users.suresh_kandru.silver_clean_str(gm_result) AS DOUBLE)) AS result_numeric,
  try_cast(users.suresh_kandru.silver_clean_str(gm_reporting_limit) AS DOUBLE) AS reporting_limit,
  users.suresh_kandru.silver_clean_str(gm_chemical_units) AS units,
  try_to_date(users.suresh_kandru.silver_clean_str(gm_samp_collection_date), 'yyyy-MM-dd') AS sample_date,
  users.suresh_kandru.silver_clean_str(src_analytical_method) AS method,
  try_cast(users.suresh_kandru.silver_clean_str(gm_latitude) AS DOUBLE) AS latitude,
  try_cast(users.suresh_kandru.silver_clean_str(gm_longitude) AS DOUBLE) AS longitude,
  try_cast(users.suresh_kandru.silver_clean_str(gm_well_depth_ft) AS DOUBLE) AS well_depth_ft
FROM users.suresh_kandru.bronze_dw_source_chemistry
WHERE users.suresh_kandru.silver_clean_str(gm_well_id) IS NOT NULL
  AND users.suresh_kandru.silver_clean_str(gm_chemical_name) IS NOT NULL
  AND try_to_date(users.suresh_kandru.silver_clean_str(gm_samp_collection_date), 'yyyy-MM-dd') IS NOT NULL;

-- Latest sample per well and chemical (what Gold serves), with the sample
-- count so callers can tell a single reading from a long record.
CREATE OR REPLACE TABLE users.suresh_kandru.silver_dw_source_chemistry_latest AS
SELECT * EXCEPT (rn)
FROM (
  SELECT
    *,
    count(*) OVER (PARTITION BY well_id, chemical_name) AS sample_count,
    row_number() OVER (
      PARTITION BY well_id, chemical_name
      ORDER BY sample_date DESC, is_non_detect ASC, result_numeric DESC NULLS LAST
    ) AS rn
  FROM users.suresh_kandru.silver_dw_source_chemistry
)
WHERE rn = 1;

-- One row per well (coordinates are constant per well; take the most recent).
CREATE OR REPLACE TABLE users.suresh_kandru.silver_dw_wells AS
SELECT
  well_id,
  any_value(pws_id) AS pws_id,
  max_by(latitude, sample_date) AS latitude,
  max_by(longitude, sample_date) AS longitude
FROM users.suresh_kandru.silver_dw_source_chemistry
WHERE latitude IS NOT NULL AND longitude IS NOT NULL
GROUP BY well_id;

-- Precomputed ZIP <-> point pairs within 50 km (haversine). The bounding-box
-- predicate (0.65 deg ~ 72 km of longitude at 42N) prunes before the trig.
CREATE OR REPLACE TABLE users.suresh_kandru.silver_dw_system_zip_pairs AS
SELECT zip, pws_id, distance_km
FROM (
  SELECT
    z.zip,
    s.pws_id,
    2 * 6371.0088 * asin(sqrt(
      pow(sin(radians(s.latitude - z.latitude) / 2), 2)
      + cos(radians(z.latitude)) * cos(radians(s.latitude))
        * pow(sin(radians(s.longitude - z.longitude) / 2), 2)
    )) AS distance_km
  FROM users.suresh_kandru.silver_zip_centroids z
  JOIN users.suresh_kandru.silver_dw_safer s
    ON abs(s.latitude - z.latitude) <= 0.65
   AND abs(s.longitude - z.longitude) <= 0.65
  WHERE s.latitude IS NOT NULL AND s.longitude IS NOT NULL
)
WHERE distance_km <= 50;

CREATE OR REPLACE TABLE users.suresh_kandru.silver_dw_well_zip_pairs AS
SELECT zip, well_id, distance_km
FROM (
  SELECT
    z.zip,
    w.well_id,
    2 * 6371.0088 * asin(sqrt(
      pow(sin(radians(w.latitude - z.latitude) / 2), 2)
      + cos(radians(z.latitude)) * cos(radians(w.latitude))
        * pow(sin(radians(w.longitude - z.longitude) / 2), 2)
    )) AS distance_km
  FROM users.suresh_kandru.silver_zip_centroids z
  JOIN users.suresh_kandru.silver_dw_wells w
    ON abs(w.latitude - z.latitude) <= 0.65
   AND abs(w.longitude - z.longitude) <= 0.65
)
WHERE distance_km <= 50;

-- Schools only carry a ZIP, so distance is centroid-to-centroid.
CREATE OR REPLACE TABLE users.suresh_kandru.silver_dw_school_zip_pairs AS
SELECT zip, school_zip, distance_km
FROM (
  SELECT
    q.zip,
    sc.zip AS school_zip,
    2 * 6371.0088 * asin(sqrt(
      pow(sin(radians(sc.latitude - q.latitude) / 2), 2)
      + cos(radians(q.latitude)) * cos(radians(sc.latitude))
        * pow(sin(radians(sc.longitude - q.longitude) / 2), 2)
    )) AS distance_km
  FROM users.suresh_kandru.silver_zip_centroids q
  JOIN users.suresh_kandru.silver_zip_centroids sc
    ON abs(sc.latitude - q.latitude) <= 0.65
   AND abs(sc.longitude - q.longitude) <= 0.65
  WHERE sc.zip IN (
    SELECT zip FROM users.suresh_kandru.silver_dw_lead_schools WHERE zip IS NOT NULL
  )
)
WHERE distance_km <= 50;
