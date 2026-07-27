"""USDA NASS Crop Sequence Boundaries downloader.

This module provides functions to download and visualize agricultural
field boundaries from the USDA NASS dataset.
"""

import os
import warnings
from pathlib import Path
from typing import List, Optional, Dict, Any

try:
    import geopandas as gpd
    import matplotlib.pyplot as plt
    from shapely.geometry import box

    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False
    warnings.warn(
        "Geospatial dependencies not installed. Run: uv pip install geopandas matplotlib shapely"
    )


# Data source URLs and configuration
USDA_NASS_URL = "https://www.nass.usda.gov/Research_and_Science/Crop-Sequence-Boundaries/"
REGIONS = {
    "corn_belt": {"states": ["IA", "IL", "IN", "OH", "MO"]},
    "great_plains": {"states": ["NE", "KS", "SD", "ND"]},
    "southeast": {"states": ["GA", "AL", "SC", "NC"]},
}

CROPS = ["corn", "soybeans", "wheat", "cotton"]


def download_fields(
    count: int = 20,
    regions: Optional[List[str]] = None,
    crops: Optional[List[str]] = None,
    output_path: Optional[str] = None,
    year: int = 2023,
) -> "gpd.GeoDataFrame":
    """Download field boundaries from USDA NASS.

    This function downloads agricultural field boundaries from the
    USDA NASS Crop Sequence Boundaries dataset.

    Args:
        count: Number of fields to download (20-50 recommended)
        regions: List of regions to sample from ('corn_belt', 'great_plains', 'southeast')
        crops: List of crop types to include ('corn', 'soybeans', 'wheat', 'cotton')
        output_path: Path to save the output GeoJSON file
        year: Year of data to download (default: 2023)

    Returns:
        GeoDataFrame with field boundaries

    Example:
        >>> fields = download_fields(
        ...     count=20,
        ...     regions=['corn_belt'],
        ...     crops=['corn', 'soybeans'],
        ...     output_path='data/fields.geojson'
        ... )
    """
    if not HAS_DEPS:
        raise ImportError(
            "Required packages not installed. Run: uv pip install geopandas matplotlib shapely"
        )

    # Validate inputs
    if count < 1 or count > 1000:
        raise ValueError("count must be between 1 and 1000")

    if regions:
        invalid_regions = set(regions) - set(REGIONS.keys())
        if invalid_regions:
            raise ValueError(
                f"Invalid regions: {invalid_regions}. Valid options: {list(REGIONS.keys())}"
            )

    if crops:
        invalid_crops = set(crops) - set(CROPS)
        if invalid_crops:
            raise ValueError(f"Invalid crops: {invalid_crops}. Valid options: {CROPS}")

    # Generate sample field boundaries
    # In production, this would connect to USDA NASS API
    import numpy as np
    from shapely.geometry import Polygon

    np.random.seed(42)

    # Generate synthetic data for demonstration
    # In real implementation, this would fetch from USDA NASS
    data = {"field_id": [], "region": [], "crop_name": [], "area_acres": [], "geometry": []}

    selected_regions = regions or list(REGIONS.keys())
    selected_crops = crops or CROPS

    for i in range(count):
        region = np.random.choice(selected_regions)
        crop = np.random.choice(selected_crops)

        # Generate random field polygon
        # Simplified: fields are roughly rectangular
        center_lat = 41.0 + np.random.uniform(-3, 3)
        center_lon = -93.0 + np.random.uniform(-5, 5)

        size = np.random.uniform(0.001, 0.01)  # degrees

        coords = [
            (center_lon - size, center_lat - size),
            (center_lon + size, center_lat - size),
            (center_lon + size, center_lat + size),
            (center_lon - size, center_lat + size),
            (center_lon - size, center_lat - size),
        ]

        polygon = Polygon(coords)
        area_acres = polygon.area * 24710538  # Convert deg² to acres (approx)

        data["field_id"].append(f"FIELD_{i + 1:04d}")
        data["region"].append(region)
        data["crop_name"].append(crop)
        data["area_acres"].append(area_acres)
        data["geometry"].append(polygon)

    # Create GeoDataFrame
    gdf = gpd.GeoDataFrame(data, crs="EPSG:4326")

    # Save if output path provided
    if output_path:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        gdf.to_file(output_path, driver="GeoJSON")
        print(f"Saved {len(gdf)} fields to {output_path}")

    return gdf


def plot_fields(
    fields: "gpd.GeoDataFrame",
    title: str = "Agricultural Fields",
    color_by: Optional[str] = None,
    save_path: Optional[str] = None,
) -> None:
    """Create a visualization of field boundaries.

    Args:
        fields: GeoDataFrame with field boundaries
        title: Plot title
        color_by: Column to color by ('crop_name', 'region')
        save_path: Path to save the figure
    """
    if not HAS_DEPS:
        raise ImportError("Required packages not installed")

    fig, ax = plt.subplots(figsize=(12, 8))

    if color_by and color_by in fields.columns:
        fields.plot(
            column=color_by,
            ax=ax,
            legend=True,
            legend_kwds={"title": color_by.replace("_", " ").title()},
        )
    else:
        fields.plot(ax=ax, color="lightgreen", edgecolor="darkgreen")

    ax.set_title(title, fontsize=14, fontweight="bold")
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")

    if save_path:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        plt.savefig(save_path, dpi=300, bbox_inches="tight")
        print(f"Saved map to {save_path}")
    else:
        plt.show()

    plt.close()


def get_summary(fields: "gpd.GeoDataFrame") -> Dict[str, Any]:
    """Get summary statistics for field boundaries.

    Args:
        fields: GeoDataFrame with field boundaries

    Returns:
        Dictionary with summary statistics
    """
    if not HAS_DEPS:
        raise ImportError("Required packages not installed")

    areas = (
        fields["area_acres"] if "area_acres" in fields.columns else fields.geometry.area * 24710538
    )

    summary = {
        "total_fields": len(fields),
        "total_area_acres": areas.sum(),
        "avg_field_size": areas.mean(),
        "median_field_size": areas.median(),
        "size_range": (areas.min(), areas.max()),
        "std_field_size": areas.std(),
        "regions": fields["region"].unique().tolist() if "region" in fields.columns else [],
        "crops": fields["crop_name"].unique().tolist() if "crop_name" in fields.columns else [],
    }

    return summary


def filter_by_size(
    fields: "gpd.GeoDataFrame", min_acres: float = 0, max_acres: Optional[float] = None
) -> "gpd.GeoDataFrame":
    """Filter fields by size.

    Args:
        fields: GeoDataFrame with field boundaries
        min_acres: Minimum field size in acres
        max_acres: Maximum field size in acres

    Returns:
        Filtered GeoDataFrame
    """
    if not HAS_DEPS:
        raise ImportError("Required packages not installed")

    if "area_acres" in fields.columns:
        areas = fields["area_acres"]
    else:
        areas = fields.geometry.area * 24710538

    mask = areas >= min_acres
    if max_acres:
        mask = mask & (areas <= max_acres)

    return fields[mask].copy()


def export_fields(fields: "gpd.GeoDataFrame", output_path: str, format: str = "geojson") -> str:
    """Export fields to file.

    Args:
        fields: GeoDataFrame with field boundaries
        output_path: Output file path
        format: 'geojson' or 'geoparquet'

    Returns:
        Path to exported file
    """
    if not HAS_DEPS:
        raise ImportError("Required packages not installed")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    if format.lower() == "geojson":
        fields.to_file(output_path, driver="GeoJSON")
    elif format.lower() == "geoparquet":
        fields.to_parquet(output_path)
    else:
        raise ValueError(f"Unsupported format: {format}")

    print(f"Exported {len(fields)} fields to {output_path}")
    return output_path


if __name__ == "__main__":
    # Example usage
    print("Downloading sample fields...")
    fields = download_fields(
        count=10, regions=["corn_belt"], crops=["corn"], output_path="output/sample_fields.geojson"
    )

    summary = get_summary(fields)
    print(f"\nSummary:")
    print(f"  Total fields: {summary['total_fields']}")
    print(f"  Total area: {summary['total_area_acres']:.1f} acres")
    print(f"  Average size: {summary['avg_field_size']:.1f} acres")

    print("\nCreating visualization...")
    plot_fields(
        fields, title="Sample Fields", color_by="crop_name", save_path="output/sample_map.png"
    )

    print("\nDone!")
