# Row Crop Intelligence Dashboard — Final Project Report

## Executive summary

The dashboard converts six completed assignments into one farmer-facing field-review workflow. Rather than presenting unrelated charts, it ranks the 25 verified fields for five practical tasks and explains why each field appears in its position. The system preserves the original data scope, makes limitations visible, and directs the user toward field verification before acting.

## Integrated sources

| Assignment | Dashboard contribution |
|---|---|
| 2 | Authoritative field IDs, acreage, and 2020–2023 dominant crop history |
| 3 | Mean classification confidence, crop transitions, and EDA relationship plot |
| 5 | Authentic Landsat NDVI for field `451623001001257` on 2023-07-27 |
| 6 | NASA POWER annual temperature and precipitation, 1991–2025 |
| 7 | Integrated field geometry and SSURGO available-water-storage attributes |
| 8 | Relative water, slope, erosion-history, rotation, and composite sustainability scores |

## Decision-support design

Five task-specific relative attention scores are calculated from verified inputs:

- **General field review:** lower soil-sustainability score increases attention.
- **Irrigation monitoring:** lower water-storage score receives greatest weight, with soil condition and slope as supporting evidence.
- **Crop scouting:** lower CDL classification confidence, lower soil score, and lower water-storage score increase attention.
- **Soil conservation:** lower sustainability, slope-resilience, and erosion-history scores increase attention.
- **Rotation planning:** lower crop-rotation diversity and lower sustainability increase attention.

These are transparent screening indices, not trained prediction models. The dashboard displays the component evidence beside every advisory.

## Farmer-oriented intelligence

The dynamic narrative system uses the selected field and management task to generate:

1. a priority label and score;
2. one or more practical follow-up actions;
3. the evidence supporting the ranking;
4. a mandatory caution to verify current field conditions.

Examples include checking soil moisture earlier after rain-free periods for relatively low-storage fields, verifying uncertain crop classifications and field edges, inspecting runoff pathways in steep or historically eroded map units, and reviewing rotation diversification where four-year diversity is low.

## Portfolio scope and key statistics

- 25 authentic fields
- 170.3 total acres
- 6 dominant soil map-unit symbols in the integrated field table
- 6 previous assignments integrated
- 5 KPI tiles
- 5 dashboard sections
- 3 interactive filter/selection mechanisms
- 8 visualizations
- 5 task rankings × 25 fields = 125 field-task priority records
- 35 annual NASA POWER records from 1991 through 2025
- One authentic NDVI field observation, retained only for its source field

## Climate context

The dashboard uses the 1991–2020 period as the descriptive baseline. In the integrated annual table, 2025 precipitation was about 14.4% below the baseline mean and annual mean temperature was about 0.45 °C above it. These values describe historical gridded conditions and are not a current forecast.

## Data engineering

A deterministic build script validates the six source files, merges field tables one-to-one on `field_id`, attaches NDVI only to its authentic field, calculates task priorities, and writes CSV, JSON, and SQLite products. The SQLite database includes indexed field and priority tables for a portable dashboard data layer.

## Validation strategy

The independent verifier:

- reloads all authoritative inputs;
- confirms exactly 25 unique fields and 35 annual weather rows;
- independently recomputes each task score;
- checks 125 field-task rankings;
- verifies SQLite row counts and indexes;
- confirms NDVI occurs for exactly one field with the authentic value;
- checks five KPI tiles, five sections, three filters, eight visualizations, and six integrated assignments;
- verifies four screenshot files and dimensions;
- rejects yield/bushel prediction fields;
- confirms all required documentation and source-attribution records.

## Interpretation limits

This is a decision-support prototype. It cannot replace scouting, a current weather forecast, soil-moisture measurements, laboratory testing, pest identification, agronomic rate calculations, or NRCS conservation planning. Its proper use is to organize and prioritize field follow-up using the evidence already available in the course repository.
