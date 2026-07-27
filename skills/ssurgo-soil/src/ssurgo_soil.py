"""USDA NRCS SSURGO soil data downloader.

This module provides functions to query SSURGO (Soil Survey Geographic Database)
soil properties for agricultural fields via the NRCS Soil Data Access (SDA)
REST API. No API key or authentication required.

Data Source:
    USDA NRCS Soil Data Access (SDA)
    https://sdmdataaccess.sc.egov.usda.gov/

Key Soil Properties:
    - Organic matter (om_r): Percentage, 0-20%
    - pH in water (ph1to1h2o_r): 3.5-10.0
    - Available water capacity (awc_r): inches/inch
    - Drainage class (drainagecl): Categorical
    - Texture: Clay/Sand/Silt percentages
    - Bulk density (dbthirdbar_r): g/cm³
    - Cation exchange capacity (cec7_r): meq/100g

Usage:
    >>> import geopandas as gpd
    >>> from ssurgo_soil import download_soil, get_soil_at_point
    >>>
    >>> fields = gpd.read_file('fields.geojson')
    >>> soil = download_soil(fields)
"""

import warnings
from pathlib import Path
from typing import Any, Optional

try:
    import geopandas as gpd
    import pandas as pd
    import requests

    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False
    warnings.warn("Required packages not installed. Run: uv pip install geopandas pandas requests")


# NRCS Soil Data Access REST API endpoint
SDA_URL = "https://sdmdataaccess.sc.egov.usda.gov/Tabular/post.rest"

# Column names returned by the SDA query (must match SELECT order)
SDA_COLUMNS = [
    "mukey",
    "muname",
    "compname",
    "comppct_r",
    "drainagecl",
    "hzdept_r",
    "hzdepb_r",
    "om_r",
    "ph1to1h2o_r",
    "awc_r",
    "claytotal_r",
    "sandtotal_r",
    "silttotal_r",
    "dbthirdbar_r",
    "cec7_r",
]

# Numeric columns for type conversion
NUMERIC_COLUMNS = [
    "comppct_r",
    "hzdept_r",
    "hzdepb_r",
    "om_r",
    "ph1to1h2o_r",
    "awc_r",
    "claytotal_r",
    "sandtotal_r",
    "silttotal_r",
    "dbthirdbar_r",
    "cec7_r",
]


def _check_deps() -> None:
    """Raise ImportError if required packages are missing."""
    if not HAS_DEPS:
        raise ImportError(
            "Required packages not installed. Run: uv pip install geopandas pandas requests"
        )


def query_sda(sql: str) -> list[dict[str, Any]]:
    """Execute a SQL query against the NRCS SDA REST API.

    The SDA REST API accepts SQL queries against the SSURGO database
    and returns results as JSON. No authentication required.

    API docs: https://sdmdataaccess.nrcs.usda.gov/WebServiceHelp.aspx

    Args:
        sql: SQL query string using SSURGO table/column names.

    Returns:
        List of dictionaries, one per result row.

    Raises:
        requests.HTTPError: If the API request fails.

    Example:
        >>> rows = query_sda("SELECT mukey, muname FROM mapunit LIMIT 5")
    """
    _check_deps()

    last_error: Optional[Exception] = None
    result: dict[str, Any] = {}
    for timeout_seconds in (60, 120):
        try:
            response = requests.post(
                SDA_URL,
                data={"query": sql, "format": "JSON"},
                timeout=timeout_seconds,
            )
            response.raise_for_status()
            result = response.json()
            break
        except Exception as exc:  # noqa: BLE001 - network retries
            last_error = exc
            continue

    if not result:
        if last_error:
            raise last_error
        return []

    if "Table" not in result:
        return []

    rows = []
    for raw_row in result["Table"]:
        row = dict(zip(SDA_COLUMNS, raw_row))
        rows.append(row)
    return rows


def _build_soil_query(wkt: str, max_depth_cm: int = 30) -> str:
    """Build SDA SQL query for soil properties at a WKT geometry.

    Args:
        wkt: WKT geometry string (POINT or POLYGON) in WGS84.
        max_depth_cm: Maximum soil depth to query (default: 30cm topsoil).

    Returns:
        SQL query string.
    """
    return f"""
    SELECT DISTINCT
        mu.mukey,
        mu.muname,
        c.compname,
        c.comppct_r,
        c.drainagecl,
        ch.hzdept_r,
        ch.hzdepb_r,
        ch.om_r,
        ch.ph1to1h2o_r,
        ch.awc_r,
        ch.claytotal_r,
        ch.sandtotal_r,
        ch.silttotal_r,
        ch.dbthirdbar_r,
        ch.cec7_r
    FROM mapunit mu
    INNER JOIN component c ON mu.mukey = c.mukey
    LEFT JOIN chorizon ch ON c.cokey = ch.cokey
    WHERE mu.mukey IN (
        SELECT * FROM SDA_Get_Mukey_from_intersection_with_WktWgs84(
            '{wkt}'
        )
    )
    AND (ch.hzdept_r < {max_depth_cm} OR ch.hzdept_r IS NULL)
    ORDER BY c.comppct_r DESC, ch.hzdept_r ASC
    """


def get_soil_at_point(
    lon: float,
    lat: float,
    max_depth_cm: int = 30,
) -> pd.DataFrame:
    """Get SSURGO soil properties at a geographic point.

    Queries the dominant soil component's horizon data at the given
    coordinates. Returns topsoil properties (0-30cm by default).

    Args:
        lon: Longitude (WGS84, decimal degrees).
        lat: Latitude (WGS84, decimal degrees).
        max_depth_cm: Maximum depth in cm (default: 30).

    Returns:
        DataFrame with soil properties. Empty if no data found.

    Example:
        >>> soil = get_soil_at_point(lon=-93.5, lat=42.0)
        >>> print(soil[['compname', 'om_r', 'ph1to1h2o_r']])
    """
    _check_deps()

    wkt = f"POINT({lon} {lat})"
    rows = query_sda(_build_soil_query(wkt, max_depth_cm))

    df = pd.DataFrame(rows)
    if not df.empty:
        for col in NUMERIC_COLUMNS:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def get_soil_for_polygon(
    wkt: str,
    max_depth_cm: int = 30,
) -> pd.DataFrame:
    """Get SSURGO soil properties for a polygon geometry.

    Queries all map units that intersect the polygon. Returns the
    dominant component's horizon properties for each map unit.

    Args:
        wkt: WKT polygon string in WGS84.
        max_depth_cm: Maximum depth in cm (default: 30).

    Returns:
        DataFrame with soil properties. Empty if no data found.

    Example:
        >>> wkt = "POLYGON((-93.5 42.0, -93.4 42.0, -93.4 42.1, -93.5 42.1, -93.5 42.0))"
        >>> soil = get_soil_for_polygon(wkt)
    """
    _check_deps()

    rows = query_sda(_build_soil_query(wkt, max_depth_cm))

    df = pd.DataFrame(rows)
    if not df.empty:
        for col in NUMERIC_COLUMNS:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def download_soil(
    fields: "gpd.GeoDataFrame",
    field_id_column: str = "field_id",
    max_depth_cm: int = 30,
    output_path: Optional[str] = None,
) -> pd.DataFrame:
    """Download SSURGO soil data for multiple field boundaries.

    For each field, queries the SDA API using the field's polygon geometry
    (or centroid as fallback) and collects soil properties.

    Args:
        fields: GeoDataFrame with field boundaries (EPSG:4326).
        field_id_column: Column name containing field IDs.
        max_depth_cm: Maximum soil depth in cm (default: 30).
        output_path: Optional path to save results as CSV.

    Returns:
        DataFrame with soil properties for all fields, including
        a 'field_id' column for joining back to field boundaries.

    Example:
        >>> import geopandas as gpd
        >>> fields = gpd.read_file('fields.geojson')
        >>> soil = download_soil(fields, output_path='soil_data.csv')
        >>> print(soil.groupby('field_id')['om_r'].mean())
    """
    _check_deps()

    all_results = []

    for idx, field in fields.iterrows():
        fid = field.get(field_id_column, f"field_{idx}")
        geom = field.geometry

        # Build WKT from geometry
        wkt = geom.wkt

        try:
            df = get_soil_for_polygon(wkt, max_depth_cm)
        except Exception:
            # Fallback to centroid if polygon query fails
            centroid = geom.centroid
            try:
                df = get_soil_at_point(centroid.x, centroid.y, max_depth_cm)
            except Exception:
                df = pd.DataFrame()

        if not df.empty:
            df["field_id"] = fid
            all_results.append(df)

    if not all_results:
        return pd.DataFrame(columns=["field_id"] + SDA_COLUMNS)

    result = pd.concat(all_results, ignore_index=True)

    if output_path:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        result.to_csv(output, index=False)

    return result


def get_dominant_soil(soil_data: pd.DataFrame) -> pd.DataFrame:
    """Extract the dominant (highest comppct_r) soil component per field.

    When multiple soil map units and components exist for a field,
    this returns only the dominant component's topmost horizon.

    Args:
        soil_data: DataFrame from download_soil().

    Returns:
        DataFrame with one row per field (dominant component, top horizon).

    Example:
        >>> soil = download_soil(fields)
        >>> dominant = get_dominant_soil(soil)
        >>> print(dominant[['field_id', 'compname', 'om_r', 'ph1to1h2o_r']])
    """
    if soil_data.empty:
        return soil_data

    # Sort by component percentage (descending) then horizon depth (ascending)
    sorted_df = soil_data.sort_values(
        ["comppct_r", "hzdept_r"],
        ascending=[False, True],
    )

    # Take first row per field (dominant component, shallowest horizon)
    return sorted_df.groupby("field_id").first().reset_index()


def classify_drainage(drainage_class: str) -> str:
    """Classify SSURGO drainage class into simple categories.

    Args:
        drainage_class: SSURGO drainage class string.

    Returns:
        One of: 'excessive', 'good', 'poor', or 'unknown'.

    Example:
        >>> classify_drainage("Well drained")
        'good'
        >>> classify_drainage("Poorly drained")
        'poor'
    """
    mapping = {
        "Excessively drained": "excessive",
        "Somewhat excessively drained": "excessive",
        "Well drained": "good",
        "Moderately well drained": "good",
        "Somewhat poorly drained": "poor",
        "Poorly drained": "poor",
        "Very poorly drained": "poor",
    }
    return mapping.get(str(drainage_class), "unknown")


try:
    from ssurgo_workflows import (  # noqa: F401
        NUMERIC_SOIL_PROPS,
        aggregate_soil_rows_by_mukey,
        classify_natural_breaks,
        headlands_ring,
        load_fallback_mukey_polygons,
        prepare_ssurgo_field_package,
        query_mupolygons_for_field,
        render_complete_workflow_figure,
        render_ssurgo_property_map,
    )
except Exception:
    pass
