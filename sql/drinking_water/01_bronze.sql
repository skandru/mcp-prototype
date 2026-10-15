-- Bronze: raw files as-is, every column a string, plus lineage columns.
-- No cleaning here; Silver owns typing and placeholders ("NULL", "NaN", ...).
-- Column names are only normalised where Delta cannot store the original
-- (spaces/parentheses in the PWS file).

CREATE OR REPLACE TABLE users.suresh_kandru.bronze_dw_pws_systems AS
SELECT
  `FOB` AS fob,
  `Region` AS region,
  `Regulating Agency` AS regulating_agency,
  `Water System No` AS water_system_no,
  `Water System Name` AS water_system_name,
  `Principal County Served` AS principal_county_served,
  `Federal Water System Type CODE` AS federal_system_type_code,
  `Federal Water System Type` AS federal_system_type,
  `State Water System Type CODE` AS state_system_type_code,
  `State Water System Type` AS state_system_type,
  `Water System Status CODE` AS status_code,
  `System Status` AS system_status,
  `Owner Type CODE` AS owner_type_code,
  `Owner Type` AS owner_type,
  `Primary Water Source Type CODE` AS primary_source_type_code,
  `Primary Water Source Type` AS primary_source_type,
  `Residential Population` AS residential_population,
  `Non-Transient Population` AS non_transient_population,
  `Transient Population` AS transient_population,
  `Total Population` AS total_population,
  `Number of Agricultural Service Connections (AG)` AS connections_ag,
  `Number of Combined Service Connections (CB)` AS connections_cb,
  `Number of Commercial Service Connections (CM)` AS connections_cm,
  `Number of Institutional Service Connections (IN)` AS connections_in,
  `Number of Residential Service Connections (RS)` AS connections_rs,
  `Total Number of Service Connections` AS total_service_connections,
  `Date of Sanitary Survey visit (SNSV Visit Date)` AS sanitary_survey_date,
  `CITY` AS city,
  `Treatment Plant Class` AS treatment_plant_class,
  `Distribution System Class` AS distribution_system_class,
  `TINWSYS_IS_NUMBER` AS tinwsys_is_number,
  _metadata.file_path AS _source_file,
  current_timestamp() AS _ingested_at
FROM read_files(
  '/Volumes/users/suresh_kandru/raw/drinking_water/current/pws_systems.csv',
  format => 'csv', header => true, inferSchema => false, multiLine => true
);

-- The SAFER file has ~140 columns with plain names; keep them all.
CREATE OR REPLACE TABLE users.suresh_kandru.bronze_dw_safer_risk_assessment AS
SELECT
  *,
  _metadata.file_path AS _source_file,
  current_timestamp() AS _ingested_at
FROM read_files(
  '/Volumes/users/suresh_kandru/raw/drinking_water/current/safer_risk_assessment.csv',
  format => 'csv', header => true, inferSchema => false, multiLine => true
);

CREATE OR REPLACE TABLE users.suresh_kandru.bronze_dw_lead_schools AS
SELECT
  *,
  _metadata.file_path AS _source_file,
  current_timestamp() AS _ingested_at
FROM read_files(
  '/Volumes/users/suresh_kandru/raw/drinking_water/current/lead_schools.csv',
  format => 'csv', header => true, inferSchema => false, multiLine => true
);

-- ~5.2M rows (1.7 GB). Not multiLine so the read can be split across workers.
CREATE OR REPLACE TABLE users.suresh_kandru.bronze_dw_source_chemistry AS
SELECT
  *,
  _metadata.file_path AS _source_file,
  current_timestamp() AS _ingested_at
FROM read_files(
  '/Volumes/users/suresh_kandru/raw/drinking_water/current/ddw_source_chemistry_2020_present.csv',
  format => 'csv', header => true, inferSchema => false
);

-- Census ZCTA gazetteer (tab-delimited). An explicit schema avoids the file's
-- padded last header name.
CREATE OR REPLACE TABLE users.suresh_kandru.bronze_zcta_centroids AS
SELECT
  *,
  _metadata.file_path AS _source_file,
  current_timestamp() AS _ingested_at
FROM read_files(
  '/Volumes/users/suresh_kandru/raw/drinking_water/current/zcta_centroids.txt',
  format => 'csv', header => true, delimiter => '\t', inferSchema => false,
  schema => 'geoid STRING, aland STRING, awater STRING, aland_sqmi STRING, awater_sqmi STRING, intptlat STRING, intptlong STRING'
);
