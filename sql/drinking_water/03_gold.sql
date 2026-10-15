-- Gold: the contract the MCP server reads (users.suresh_kandru.v_*).
-- Views are thin joins over Silver; zip + distance_km come precomputed from the
-- Silver pair tables so the server never does geospatial math per request.
-- No street addresses, phone numbers or other PII are exposed.
-- source_url is a data.ca.gov datastore query that returns the underlying
-- record(s) for the row.

-- One row per public water system, with SAFER risk status where assessed.
CREATE OR REPLACE VIEW users.suresh_kandru.v_water_systems
COMMENT 'California public water systems (SDWIS inventory) joined to SAFER risk assessment and violation flags. One row per pws_id. Refreshed when the pipeline reloads the CA Water Boards open data; see data_as_of.'
AS
SELECT
  s.pws_id,
  s.system_name,
  s.county,
  s.city,
  s.federal_type,
  s.state_type,
  s.status,
  s.owner_type,
  s.primary_source_type,
  s.total_population,
  s.service_connections,
  s.last_sanitary_survey,
  r.latitude,
  r.longitude,
  r.safer_status,
  r.is_failing,
  r.failing_start_date,
  r.risk_assessment_result,
  r.economic_status,
  r.median_household_income,
  r.has_primary_mcl_violation,
  r.primary_mcl_analytes,
  r.has_secondary_mcl_violation,
  r.secondary_mcl_analytes,
  r.has_ecoli_violation,
  r.ecoli_analytes,
  r.has_treatment_technique_violation,
  r.treatment_technique_analytes,
  r.has_monitoring_violation,
  r.monitoring_violation_analytes,
  r.water_quality_risk_level,
  r.accessibility_risk_level,
  r.affordability_risk_level,
  r.tmf_capacity_risk_level,
  r.total_weighted_risk_score,
  r.pws_id IS NOT NULL AS has_risk_assessment,
  coalesce(r.data_as_of, s.data_as_of) AS data_as_of,
  concat(
    'https://data.ca.gov/api/3/action/datastore_search?resource_id=',
    '5af27515-f0da-4cc9-92c5-0cd8eeee6843&q=', s.pws_id
  ) AS source_url
FROM users.suresh_kandru.silver_dw_systems s
LEFT JOIN users.suresh_kandru.silver_dw_safer r USING (pws_id);

-- Systems located within 50 km of a ZIP centroid (only assessed systems have
-- coordinates).
CREATE OR REPLACE VIEW users.suresh_kandru.v_water_systems_near_zip
COMMENT 'Public water systems within 50 km of a ZIP centroid, with SAFER status and violation flags. Filter on zip and distance_km.'
AS
SELECT p.zip, p.distance_km, v.*
FROM users.suresh_kandru.silver_dw_system_zip_pairs p
JOIN users.suresh_kandru.v_water_systems v USING (pws_id);

-- Latest result per drinking-water source well and chemical.
CREATE OR REPLACE VIEW users.suresh_kandru.v_source_chemistry_latest
COMMENT 'Latest DDW/GAMA source-water (well) chemistry result per well and chemical, 2020-present. Raw source water before treatment, not tap water. Non-detects have is_non_detect = true and result_numeric NULL; compare against reporting_limit.'
AS
SELECT
  c.pws_id,
  sys.system_name,
  c.well_id,
  c.county,
  c.well_category,
  c.chemical_name,
  c.cas_number,
  c.is_non_detect,
  c.result_numeric,
  c.reporting_limit,
  c.units,
  c.sample_date AS last_observed,
  c.sample_count,
  c.method,
  c.latitude,
  c.longitude,
  c.well_depth_ft,
  concat(
    'https://data.ca.gov/api/3/action/datastore_search?resource_id=',
    'd2e74ace-2cf4-4baf-aadd-406280bf1c1c&q=', c.well_id
  ) AS source_url
FROM users.suresh_kandru.silver_dw_source_chemistry_latest c
LEFT JOIN users.suresh_kandru.silver_dw_systems sys USING (pws_id);

CREATE OR REPLACE VIEW users.suresh_kandru.v_source_chemistry_near_zip
COMMENT 'Latest source-water chemistry per well and chemical for wells within 50 km of a ZIP centroid. Filter on zip, distance_km, and optionally chemical_name.'
AS
SELECT p.zip, p.distance_km, c.*
FROM users.suresh_kandru.silver_dw_well_zip_pairs p
JOIN users.suresh_kandru.v_source_chemistry_latest c USING (well_id);

-- K-12 school lead sampling (2020 onward), located by the school's ZIP.
CREATE OR REPLACE VIEW users.suresh_kandru.v_school_lead_near_zip
COMMENT 'Lead-in-drinking-water samples at California K-12 schools (2020 onward) for schools within 50 km of a ZIP centroid. Distance is ZIP-centroid to ZIP-centroid. action_level_exceeded is the state flag.'
AS
SELECT
  p.zip,
  p.distance_km,
  l.pws_id,
  l.water_system_name,
  l.district,
  l.school_name,
  l.sample_location,
  l.zip AS school_zip,
  l.school_county,
  l.school_type,
  l.is_non_detect,
  l.result_numeric,
  l.reporting_limit,
  l.units,
  l.action_level_exceeded,
  l.follow_up_action,
  l.follow_up_status,
  l.sample_date AS last_observed,
  concat(
    'https://data.ca.gov/api/3/action/datastore_search?resource_id=',
    '5ebb2d68-1186-4937-acaf-8564c9a01ed6&q=', l.pws_id
  ) AS source_url
FROM users.suresh_kandru.silver_dw_school_zip_pairs p
JOIN users.suresh_kandru.silver_dw_lead_schools l ON l.zip = p.school_zip;
