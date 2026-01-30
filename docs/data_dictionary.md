# Cape Town Eco-Property: Data Dictionary
# Generated: 2026-01-30
# Source: City of Cape Town Open Data Portal (https://odp-cctegis.opendata.arcgis.com)

## cct_coastal_urban_edge_2025
Description: Coastal Urban Edge boundary
CRS: EPSG:3857
Feature Service: https://esapqa.capetown.gov.za/agsext/rest/services/Theme_Based/ODP_SPLIT_3/FeatureServer/10
GeoJSON Size: 492,785 bytes (0.5 MB)
Geometry Type: LineString/MultiLineString
Field Count: 3
Fields:
  - OBJECTID (OID): OBJECTID
  - PRMT_MTR (Double): Perimeter (m)
  - Shape__Length (Double): Shape.STLength()
Last Edit Date: Unknown

## cct_environmental_focus_areas_2025
Description: Environmental Focus Areas
CRS: EPSG:3857
Feature Service: https://esapqa.capetown.gov.za/agsext/rest/services/Theme_Based/ODP_SPLIT_11/FeatureServer/18
GeoJSON Size: 542,603 bytes (0.5 MB)
Geometry Type: Polygon/MultiPolygon
Field Count: 6
Fields:
  - OBJECTID (OID): OBJECTID
  - DSCR (String): Description
  - NAME (String): Name
  - AREA_HCTR (Double): Area (ha)
  - Shape__Area (Double): Shape.STArea()
  - Shape__Length (Double): Shape.STLength()
Last Edit Date: Unknown

## cct_heritage_inventory_2025
Description: Heritage Inventory - protected structures
CRS: EPSG:3857
Feature Service: https://esapqa.capetown.gov.za/agsext/rest/services/Theme_Based/ODP_SPLIT_3/FeatureServer/2
GeoJSON Size: 135,863,219 bytes (129.6 MB)
Geometry Type: Polygon/MultiPolygon
Field Count: 38
Fields:
  - OBJECTID (OID): OBJECTID
  - HRTG_INV_SITE_NAME (String): Site Name
  - HRTG_INV_RCS_CAT (Integer): Heritage Category
  - HRTG_INV_RCS_TYPE_1 (String): Heritage Resource Type1
  - HRTG_INV_RCS_TYPE_2 (String): Heritage Resource Type2
  - SITE_DSRP (String): Site Description
  - ARL_CHK (String): Aerial Check
  - SXTY_YEAR (String): Sixty Year
  - BLT_ENV (String): Original Use
  - ARCH_STYL (String): Architectural Style
  - PRD (String): Period
  - GRDN_NTS (String): Grading Notes
  - NHRA_STS (String): Formal NHRA Status
  - GNRL_NHRA_PRTC (String): General NHRA Protection
  - NHRA_EXMT (String): NHRA Exemptions
  - PRSD_CITY_GRD (String): Proposed City Grade
  - CNFR_CCT_GRD (String): City Grading
  - CNFR_CCT_MGNT_GD (String): City Management Guide
  - HPZ_EXMP (String): HPOZ Site Exemption Level
  - PRPD_HPZ_EXMP (String): Proposed HPOZ Site Exemption Level
  - INT_SNFC (String): Significant Interior
  - INT_DSRP (String): Interior Description
  - STMN_SGNF_SHRT (String): Statement of Significance
  - ASTH_SGNF (String): Aesthetic Significance
  - ARCH_SGNF (String): Architectural Significance
  - ASC_SGNF (String): Associational Significance
  - CNTX_SGNF (String): Contextual Significance
  - SYMB_SGNF (String): Symbolic Significance
  - RTY_SGNF (String): Rarity
  - RPRS_SGNF (String): Representivity
  - GRPN_SGNF (String): Part of Grouping
  - STR_ADR (String): Street Address
  - AGE_SGNF (String): Age Significance
  - EXCL_SGNF (String): Excellence Significance
  - SCNT_SGNF (String): Scientific Significance
  - RCMD_NHRA (String): Recommended for Formal Protection
  - Shape__Area (Double): SHAPE.STArea()
  - Shape__Length (Double): SHAPE.STLength()
Last Edit Date: Unknown

## cct_indigenous_vegetation_current_2025
Description: Indigenous Vegetation - Current Extent
CRS: EPSG:3857
Feature Service: https://esapqa.capetown.gov.za/agsext/rest/services/Theme_Based/ODP_SPLIT_3/FeatureServer/11
GeoJSON Size: 32,196,176 bytes (30.7 MB)
Geometry Type: Polygon/MultiPolygon
Field Count: 10
Fields:
  - OBJECTID (OID): OBJECTID
  - NTNL_VGTN_TYPE (Integer): National Vegetation Type
  - VGTN_SBTY (Integer): Vegetation Subtype
  - CMNT (Integer): Community
  - AREA_HCTR (Double): Area (ha)
  - PRMT_MTR (Double): Perimeter (m)
  - DATE_ADD (Date): Date added
  - DATE_CHNG (Date): Date changed
  - Shape__Area (Double): Shape.STArea()
  - Shape__Length (Double): Shape.STLength()
Last Edit Date: Unknown

## cct_land_parcels_2025
Description: Land Parcels - cadastral/erf boundaries
CRS: EPSG:3857
Feature Service: https://esapqa.capetown.gov.za/agsext/rest/services/Theme_Based/ODP_SPLIT_4/FeatureServer/0
GeoJSON Size: 824,425,777 bytes (786.2 MB)
Geometry Type: Polygon/MultiPolygon
Field Count: 16
Fields:
  - OBJECTID (OID): OBJECTID
  - SG26_CODE (String): SG26 Code
  - SL_LAND_PRCL_KEY (Integer): ISIS / LIS Key
  - ADR_NO (Integer): Address No
  - ADR_NO_SFX (String): Address No Suffix
  - STR_NAME (String): Street Name
  - LU_STR_NAME_TYPE (String): Street Name Type
  - OFC_SBRB_NAME (String): Official Suburb Name
  - ALT_NAME (String): Allotment Name
  - WARD_NAME (String): Ward Name
  - LU_LGL_STS_DSCR (String): Legal Status SG
  - PRTY_NMBR (String): Property Number
  - ZONING (String): Zoning Description
  - SUB_CNCL_NMBR (String): Subcouncil Number
  - Shape__Area (Double): SHAPE.STArea()
  - Shape__Length (Double): SHAPE.STLength()
Last Edit Date: Unknown

## cct_nhra_protection_2025
Description: National Heritage Resources Act formal protections
CRS: EPSG:3857
Feature Service: https://esapqa.capetown.gov.za/agsext/rest/services/Theme_Based/ODP_SPLIT_3/FeatureServer/0
GeoJSON Size: 1,030,092 bytes (1.0 MB)
Geometry Type: Polygon/MultiPolygon
Field Count: 12
Fields:
  - OBJECTID (OID): OBJECTID
  - LU_NHRA_STS (String): NHRA Status
  - LU_NMC_STS (String): Old NMA Status
  - NMC_PRCL (Date): NMA Gazette (Pre 2000)
  - NMC_PRCL_2000 (Date): NMA Gazette 2 (Pre 2000)
  - SITE_NAME (String): Site Name
  - STMT_SGNF_SHRT (String): Statement of Significance
  - NTNL_GZT (Date): National Gazette (Post 2000)
  - PRVC_GZT (Date): Provincial Gazette (Post 2000)
  - GZT_TXT (String): Gazette Wording (Post 2000)
  - Shape__Area (Double): Shape.STArea()
  - Shape__Length (Double): Shape.STLength()
Last Edit Date: Unknown

## cct_rainfall_from_2000
Description: Daily rainfall time series from 2000 onwards (CSV)
Type: Tabular (CSV)
Portal URL: https://odp-cctegis.opendata.arcgis.com/datasets/cctegis::rainfall-data-from-2000
Note: CSV - download from portal or access via API

## cct_sanbi_ecosystem_status_2011
Description: SANBI Vegetation Ecosystem Threat Status 2011
CRS: EPSG:3857
Feature Service: https://esapqa.capetown.gov.za/agsext/rest/services/Theme_Based/ODP_SPLIT_3/FeatureServer/13
GeoJSON Size: 32,467,559 bytes (31.0 MB)
Geometry Type: Polygon/MultiPolygon
Field Count: 10
Fields:
  - OBJECTID (OID): OBJECTID
  - NTNL_VGTN_TYPE (String): National Vegatation Type
  - VGTN_SBTY (String): Vegetation Subtype
  - CMNT (String): Community
  - AREA_HCTR (Double): AREA (ha)
  - PRMT_MTR (Double): Perimeter (m)
  - ECSY_STS_2011 (String): Ecosystem Status 2011
  - VGTN_NTNL_TYPE_INTG (Integer): VGTN_NTNL_TYPE_INTG
  - Shape__Area (Double): SHAPE.STArea()
  - Shape__Length (Double): SHAPE.STLength()
Last Edit Date: Unknown

## cct_smartfacility_solar_2025
Description: SmartFacility Solar installations
CRS: EPSG:3857
Feature Service: https://esapqa.capetown.gov.za/agsext/rest/services/Theme_Based/ODP_SPLIT_10/FeatureServer/13
GeoJSON Size: 544,160 bytes (0.5 MB)
Geometry Type: Point/MultiPoint
Field Count: 18
Fields:
  - OBJECTID (OID): ID
  - LIS_KEY (Integer): LIS Key
  - ALTR_BLDN_NAME (String): Alternative Building Name
  - FCLT_TYPE_DSCR (String): Facility Type Description
  - DPRT_DSCR (String): Department Description
  - FCLT_Y_CRDN (Double): Facility Coordinate Latitude
  - FCLT_X_CRDN (Double): Facility Coordinate Longitude
  - PRTY_Y_CRDN (Double): Property Coordinate Latitude
  - PRTY_X_CRDN (Double): Property Coordinate Longitude
  - SF_BLDN_USE_SPC (Double): SF Building Use Space
  - LAST_RDNG_DATE_TIME (Date): Last Reading Date Timestamp
  - CLND_YEAR (SmallInteger): Calendar Year
  - CLND_MNTH_NMBR (SmallInteger): Calendar Month Number
  - MNTH_DATE_RCRD (String): Monthly Date Recorded
  - MNTH_SLR_GNRT (Double): Monthly Solar Generated
  - MNTH_CRBN_SVD (Double): Monthly Carbon Saved
  - ANL_SLR_GNRT (Double): Annual Solar Generated
  - ANL_CRBN_SVD (Double): Annual Carbon Saved
Last Edit Date: Unknown

## cct_solar_exports_2014_2023
Description: Customer solar energy exports 2014-2023 (CSV)
Type: Tabular (CSV)
Portal URL: https://odp-cctegis.opendata.arcgis.com/datasets/cctegis::customer-solar-energy-exports-2014-to-2023
Note: CSV - download from portal or access via API

## cct_split_zoning_2025
Description: Split Zoning - properties with multiple zoning classifications
CRS: EPSG:3857
Feature Service: https://esapqa.capetown.gov.za/agsext/rest/services/Theme_Based/ODP_SPLIT_4/FeatureServer/1
GeoJSON Size: 26,222,561 bytes (25.0 MB)
Geometry Type: Polygon/MultiPolygon
Field Count: 9
Fields:
  - OBJECTID (OID): OBJECTID
  - LU_IZNG_CD_KEY (Integer): LU_IZNG_CD_KEY
  - STS (Integer): Status
  - SL_ZNG_SPLT_KEY (Integer): SL_ZNG_SPLT_KEY
  - INT_ZONE_VALUE (Integer): Integrated Zoning Value
  - INT_ZONE_CODE (String): Integrated Zoning Code
  - INT_ZONE_DESC (String): Integrated Zone Description
  - Shape__Area (Double): SHAPE.STArea()
  - Shape__Length (Double): SHAPE.STLength()
Last Edit Date: Unknown

## cct_street_address_numbers_2025
Description: Street Address Numbers - geocoding reference points
CRS: EPSG:3857
Feature Service: https://esapqa.capetown.gov.za/agsext/rest/services/Theme_Based/ODP_SPLIT_6/FeatureServer/1
GeoJSON Size: 366,981,581 bytes (350.0 MB)
Geometry Type: Point/MultiPoint
Field Count: 12
Fields:
  - OBJECTID (OID): OBJECTID
  - ADR_NO (Integer): Address Number
  - ADR_NO_PRF (String): Address Number Prefix
  - ADR_NO_SFX (String): Address Number Suffix
  - OFC_SBRB_NAME (String): Official Suburb Name
  - STR_NAME (String): Street Name
  - LU_STR_NAME_TYPE (String): Street Name Type
  - LU_LIFE_CL_STG_KEY (Integer): Address Life Cycle Stage
  - LU_ADR_STS_KEY (Integer): Address Status
  - LU_ADR_TYPE_KEY (Integer): Address Type
  - SL_CMPL_EST_KEY (Integer): Complex Estate
  - FULL_ADR (String): Full Address
Last Edit Date: Unknown

## cct_terrestrial_biodiversity_network_2025
Description: Terrestrial Biodiversity Network (BioNet) - CBA classifications for Cape Town
CRS: EPSG:3857
Feature Service: https://esapqa.capetown.gov.za/agsext/rest/services/Theme_Based/ODP_SPLIT_3/FeatureServer/9
GeoJSON Size: 94,675,906 bytes (90.3 MB)
Geometry Type: Polygon/MultiPolygon
Field Count: 24
Fields:
  - OBJECTID (OID): OBJECTID
  - CBA_CTGR (String): Critical Biodiversity Area category
  - CBA_NAME (String): CBA Name
  - SBTY (String): Subtype
  - SDF_CTGR (String): Spatial Development Framework category
  - CBA_DSCR (String): CBA Description
  - SGNF_HBT (String): Significance of Habitat
  - OBJC (String): Objective
  - ACTN (String): Action
  - CMPT_ACTV (String): Compatible Activities
  - HBT_CNDT (String): Habitat Condition
  - DATE_GRND_TRTH (Date): Date Groundtruthed
  - GRND_TRTH_BY (String): Groundtruthed By
  - CESA_SGNF (String): Significance of ESA
  - NAME_PRTC_AREA (String): Name of Protected Area
  - PRCL (String): Proclaimed/In Process
  - MNGD (String): Managed
  - PRMR_CLS (String): Primary Class of Protected Area
  - SCND_CLS (String): Secondary Class of Protected Area
  - TRTR_CLS (String): Tertiary Class of Protected Area
  - AREA_HCTR (Double): Area (ha)
  - PRMT_MTR (Double): Perimeter (m)
  - Shape__Area (Double): SHAPE.STArea()
  - Shape__Length (Double): SHAPE.STLength()
Last Edit Date: Unknown

## cct_urban_development_edge_2025
Description: Urban Development Edge boundary
CRS: EPSG:3857
Feature Service: https://esapqa.capetown.gov.za/agsext/rest/services/Theme_Based/ODP_SPLIT_11/FeatureServer/12
GeoJSON Size: 1,212,521 bytes (1.2 MB)
Geometry Type: Polygon/MultiPolygon
Field Count: 5
Fields:
  - OBJECTID (OID): OBJECTID
  - DSCR (String): Description
  - AREA_HCTR (Double): Area (ha)
  - Shape__Area (Double): Shape.STArea()
  - Shape__Length (Double): Shape.STLength()
Last Edit Date: Unknown

## cct_wetlands_2025
Description: Wetlands - aquatic biodiversity network features
CRS: EPSG:3857
Feature Service: https://esapqa.capetown.gov.za/agsext/rest/services/Theme_Based/ODP_SPLIT_3/FeatureServer/15
GeoJSON Size: 26,342,318 bytes (25.1 MB)
Geometry Type: Polygon/MultiPolygon
Field Count: 37
Fields:
  - OBJECTID (OID): OBJECTID
  - WTLN_ID (String): WTLN_ID
  - WTLN_NAME (String): Wetland Name
  - ANTH_TYPE (Integer): Anthropological Type
  - CBA_CTGR (Integer): Critical Biodiversity Area category
  - LVL_1 (Integer): Level 1
  - LVL_2 (Integer): Level 2
  - LVL_3 (Integer): Level 3
  - LVL_4A (Integer): Level 4A
  - LVL_4B (Integer): Level 4B
  - LVL_4C (Integer): Level 4C
  - LVL_5A (Integer): Level 5A
  - LVL_5B (Integer): Level 5B
  - LVL_5C (Integer): Level 5C
  - LVL_6A (Integer): Level 6A
  - LVL_6B (Integer): Level 6B
  - LVL_6C (Integer): Level 6C
  - LVL_6E (Integer): Level 6E
  - VGTN_INDG_CMNT (String): Dominant Indigenous Vegetation
  - VGTN_ALN_CMNT (String): Dominant Alien Vegetation
  - SBST (Integer): Substrate
  - SLNT (Integer): Salinity
  - PH (Integer): PH
  - PES (Integer): Present Ecological Status
  - EIS (Integer): Ecological Importance and Sensitivity
  - IMPC (Integer): Dominant modification
  - IMPC_CMNT (String): Modification comments
  - CMNT (String): General comments
  - EXPR_RVWR (String): Expert Reviewer
  - TO_GRND_TRTH (Integer): To groundtruth
  - GRND_TRTH_BY (String): Groundtruthed by
  - DATE_GRND_TRTH (Date): Date groundtruthed
  - MAP_CNFD (Integer): Confidence in mapping
  - AREA_HCTR (Double): Area (ha)
  - PRMT_MTR (Double): Perimeter (m)
  - Shape__Area (Double): Shape.STArea()
  - Shape__Length (Double): Shape.STLength()
Last Edit Date: Unknown

## cct_zoning_2025
Description: City Zoning - current zoning scheme boundaries
CRS: EPSG:3857
Feature Service: https://esapqa.capetown.gov.za/agsext/rest/services/Theme_Based/ODP_SPLIT_5/FeatureServer/0
GeoJSON Size: 673,076,321 bytes (641.9 MB)
Geometry Type: Polygon/MultiPolygon
Field Count: 10
Fields:
  - OBJECTID (OID): OBJECTID
  - SL_LAND_PRCL_KEY (Integer): ISIS / LIS Key
  - SG26_CODE (String): SG26 Code
  - LU_IZNG_CD_KEY (Integer): Integrated Zoning Code Key
  - INT_ZONE_VALUE (Integer): Integrated Zoning Value
  - INT_ZONE_CODE (String): Integrated Zoning Code
  - INT_ZONE_DESC (String): Integrated Zoning Description
  - LU_LGL_STS_KEY (Integer): Legal Status
  - Shape__Area (Double): SHAPE.STArea()
  - Shape__Length (Double): SHAPE.STLength()
Last Edit Date: Unknown

