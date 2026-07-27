---
name: ag-data-analysis-skills
description: Agricultural data analysis skills for downloading and analyzing US agricultural datasets. Includes tools for field boundaries, soil data, weather data, satellite imagery, crop data, and exploratory data analysis.
version: 1.0.0
author: Boreal Bytes
tags: [agriculture, usda, data-analysis, geospatial, remote-sensing]
---

# Agricultural Data Analysis Skills

## Overview

This collection provides AI-ready skills for downloading and analyzing US agricultural data. All skills use standard Python libraries (pandas, geopandas, matplotlib, xarray) with no custom wrappers - just real library code.

## Skill Categories

### Data Download Skills (With Python Code)

These skills download real data and run in isolated environments using UV:

#### Required First: Field Boundaries

**Skill**: `field-boundaries`
**Purpose**: Download USDA NASS Crop Sequence Boundaries
**Prerequisites**: None
**Use this first**: All other download skills reference field boundaries
**Example**: Download 2 fields from Corn Belt

```bash
uv run --with geopandas python << 'EOF'
from field_boundaries import download_fields
fields = download_fields(count=2, regions=['corn_belt'])
fields.to_file('my_fields.geojson')
EOF
```

#### Soil Data

**Skill**: `ssurgo-soil`
**Purpose**: Download USDA NRCS SSURGO soil data
**Prerequisites**: field-boundaries (uses field polygons for spatial queries)
**Data**: Soil properties (pH, organic matter, texture, drainage)
**Example**: Get soil data for downloaded fields

#### Weather Data

**Skill**: `nasa-power-weather`
**Purpose**: Download NASA POWER weather data
**Prerequisites**: field-boundaries (uses field centroids for point queries)
**Data**: Temperature, precipitation, solar radiation, humidity
**Example**: Get 2020-2024 weather for field locations

#### Crop Data

**Skill**: `cdl-cropland`
**Purpose**: Download USDA NASS Cropland Data Layer
**Prerequisites**: field-boundaries (optional, for filtering)
**Data**: Annual crop type maps at 30m resolution
**Example**: Get crop history for 2015-2024

#### Satellite Imagery

**Skills**: `sentinel2-imagery`, `landsat-imagery`
**Purpose**: Download satellite imagery from ESA/USGS
**Prerequisites**: field-boundaries (for area of interest)
**Data**: Multispectral imagery, NDVI time series
**Example**: Get NDVI for growing season 2023

#### Interactive Maps

**Skill**: `interactive-web-map`
**Purpose**: Create interactive web maps
**Prerequisites**: field-boundaries (for visualization)
**Use**: Combine with downloaded data for interactive exploration

### Analysis Skills (Markdown with Code Examples)

These skills teach how to use standard Python libraries:

#### Exploratory Data Analysis

**Skills**: `eda-explore`, `eda-visualize`, `eda-correlate`, `eda-time-series`, `eda-compare`
**Purpose**: Learn pandas, matplotlib, seaborn for agricultural data
**Prerequisites**: None (uses any CSV data)
**Examples**:

- Explore: Generate descriptive statistics
- Visualize: Create histograms, scatter plots, heatmaps
- Correlate: Calculate correlation matrices
- Time Series: Analyze trends over time
- Compare: Compare groups statistically

## Quick Start Workflow

### Step 1: Download Field Boundaries (Required First)

```bash
cd .skills/field-boundaries
uv run --with geopandas python << 'EOF'
from field_boundaries import download_fields

# Download 2 fields
fields = download_fields(
    count=2,
    regions=['corn_belt'],
    crops=['corn', 'soybeans'],
    output_path='examples/my_fields.geojson'
)

print(f"Downloaded {len(fields)} fields")
EOF
```

### Step 2: Get Soil Data for Those Fields

```bash
cd .skills/ssurgo-soil
uv run --with geopandas python << 'EOF'
from ssurgo_soil import get_soil_for_fields

# Get soil data using the field boundaries
soil = get_soil_for_fields(
    fields_path='../field-boundaries/examples/my_fields.geojson',
    output_path='soil_data.csv'
)

print(f"Retrieved soil data: {len(soil)} records")
EOF
```

### Step 3: Analyze with EDA

```python
import pandas as pd
import matplotlib.pyplot as plt

# Load soil data
soil = pd.read_csv('.skills/ssurgo-soil/examples/soil_data.csv')

# Explore
print(soil.describe())

# Visualize
plt.figure(figsize=(10, 6))
plt.hist(soil['ph_water'], bins=20, edgecolor='black')
plt.title('Soil pH Distribution')
plt.xlabel('pH Level')
plt.savefig('ph_distribution.png', dpi=300)
```

## Dependency Chain

```
field-boundaries (REQUIRED FIRST)
    │
    ├──> ssurgo-soil (needs field polygons)
    │
    ├──> nasa-power-weather (needs field locations)
    │
    ├──> cdl-cropland (optional: can use fields for AOI)
    │
    ├──> sentinel2-imagery (needs AOI from fields)
    │
    ├──> landsat-imagery (needs AOI from fields)
    │
    └──> interactive-web-map (visualizes field data)

eda-* skills (independent - work with any CSV)
```

## Environment Setup

Each data download skill runs in an isolated environment:

```bash
# Install UV
curl -LsSf https://astral.sh/uv/install.sh | sh

# For any skill:
cd .skills/<skill-name>
uv run --with <packages> python <script.py>
```

## Example Data

Each skill includes minimal real data in `examples/`:

- **field-boundaries/examples/**: 2 real field boundaries from USDA
- **ssurgo-soil/examples/**: Soil data for the 2 fields
- **nasa-power-weather/examples/**: Weather for the 2 fields
- etc.

These examples serve as:

- Tests (verify the skill works)
- Documentation (show expected output)
- Development (AI can reference for patterns)

## Data Sources

| Data             | Provider   | Format     | Update     |
| ---------------- | ---------- | ---------- | ---------- |
| Field Boundaries | USDA NASS  | GeoParquet | Annual     |
| Soil             | USDA NRCS  | Tabular    | Varies     |
| Weather          | NASA POWER | NetCDF     | Daily      |
| Crops            | USDA NASS  | GeoTIFF    | Annual     |
| Imagery          | ESA/USGS   | GeoTIFF    | Days/Weeks |

All data is **public domain** or **free for research use**.
All data is **public domain** or **free for research use**.

## Data Output Standards

### Directory Structure

```
.skill-name/
├── data/                    # Gitignored - generated outputs
│   ├── README.md           # Documents what data is here
│   ├── fields_2024.geojson
│   ├── soil_analysis.csv
│   └── plots/
│       ├── field_sizes.png
│       └── ph_distribution.png
├── scripts/                # Python scripts for generating data
│   ├── download_fields.py
│   ├── analyze_soil.py
│   └── create_plots.py
├── examples/               # Committed sample data (small, <1MB)
│   ├── sample_2_fields.geojson
│   └── sample_output.png
└── SKILL.md
```

### Rules

1. **`data/` folder is Gitignored** - Never commit large data files
2. **Save Python scripts** - Every output must have its generating script in `scripts/`
3. **Data provenance** - Scripts document how data was created
4. **Small examples only** - Only `examples/` is committed (≤2 fields)
5. **Descriptive naming** - `fields_{date}_{region}.geojson`

### .gitignore Template

```gitignore
# Data outputs - never commit
data/
*.geojson
*.tif
*.nc
*.csv
*.png
*.jpg
*.pdf

# Large binary files
*.parquet
*.shp
*.shx
*.dbf

# Except examples
!examples/*
!examples/**/*
```

### Example Workflow

```python
# scripts/download_and_analyze.py
"""Download fields and create analysis outputs.

This script downloads field boundaries and creates:
- data/fields_2024.geojson
- data/summary_statistics.csv
- data/plots/field_sizes.png
"""

import pandas as pd
import geopandas as gpd
from pathlib import Path

# Create output directories
Path('data/plots').mkdir(parents=True, exist_ok=True)

# Download data
fields = download_fields(count=20, regions=['corn_belt'])
fields.to_file('data/fields_2024.geojson')

# Create analysis
summary = fields.describe()
summary.to_csv('data/summary_statistics.csv')

# Create plots
import matplotlib.pyplot as plt
plt.figure(figsize=(10, 6))
fields['area_acres'].hist(bins=20)
plt.title('Field Size Distribution')
plt.savefig('data/plots/field_sizes.png', dpi=300, bbox_inches='tight')
plt.close()

print("Created:")
print("  - data/fields_2024.geojson")
print("  - data/summary_statistics.csv")
print("  - data/plots/field_sizes.png")
```

### Data README Template

Each `data/` folder should have a README:

```markdown
# Data Outputs

This directory contains generated data. DO NOT COMMIT TO GIT.

## Contents

| File | Script | Description |
|------|--------|-------------|
| fields_2024.geojson | download_fields.py | 20 corn belt fields |
| summary_stats.csv | analyze_fields.py | Statistical summary |
| plots/*.png | visualize.py | Generated plots |

## Regeneration

To recreate this data:

```bash
cd scripts
python download_fields.py
python analyze_fields.py
python visualize.py
```
```

## Best Practices
## Best Practices

### For Data Download Skills:

1. **Always start with field-boundaries**
2. **Use small counts** (2-10) for testing
3. **Save outputs** with descriptive names
4. **Check file sizes** before committing
5. **Use GeoJSON** for sharing, GeoParquet for storage

### For EDA Skills:

1. **Use real libraries** (pandas, matplotlib)
2. **Start with examples/sample data**
3. **Save outputs** to organized directories
4. **Document what you analyze**

### General:

- **UV for isolation**: Each skill in its own environment
- **Small test data**: 2 fields is enough for testing
- **Real data only**: Download from actual sources
- **Git LFS**: Use for binary files (.geotiff, .parquet)

## Troubleshooting

### "ImportError: No module named..."

**Fix**: You're not in the skill's isolated environment

```bash
cd .skills/<skill-name>
uv run --with <package> python
```

### "No fields returned"

**Fix**: Relax filters (increase count, remove size limits)

```python
fields = download_fields(count=10)  # Simpler query
```

### "Slow downloads"

**Fix**: Reduce count or add filters

```python
fields = download_fields(count=2)  # Fewer = faster
```

## Resources

- **Source Cooperative**: https://source.coop/fiboa/us-usda-cropland
- **USDA NASS**: https://www.nass.usda.gov
- **NASA POWER**: https://power.larc.nasa.gov
- **USGS Earth Explorer**: https://earthexplorer.usgs.gov
- **Sentinel Hub**: https://www.sentinel-hub.com

## Citation

```
USDA National Agricultural Statistics Service Cropland Data Layer. 2023.
Published crop-specific data layer [Online].
Available at https://nassgeodata.gmu.edu/CropScape/
```

## Support

For issues or questions:

- **GitHub Issues**: https://github.com/borealBytes/ag-skills/issues
- **Documentation**: See individual skill SKILL.md files
