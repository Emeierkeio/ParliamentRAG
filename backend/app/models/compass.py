"""
Compass data models for the ideological compass pipeline.

Defines all Pydantic models used in the IC-1 to IC-6 pipeline.
"""
from typing import List, Dict, Optional, Any
from enum import Enum
from dataclasses import dataclass, field

from pydantic import BaseModel, Field


class CompassDimensionality(int, Enum):
    """Dimensionality of the compass visualization."""
    ONE_D = 1
    TWO_D = 2


class AxisSideDescription(BaseModel):
    """Description of one side (pole) of an axis."""
    label: str = Field(description="Short label for this pole")
    explanation: str = Field(description="Longer explanation of what this pole represents")
    keywords: List[str] = Field(default_factory=list, description="Key terms associated with this pole")
    fragments: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Top fragments representing this pole"
    )


class AxisDefinition(BaseModel):
    """Definition of a PCA axis with interpretability info."""
    index: int = Field(description="Axis index (0=PC1, 1=PC2)")
    explained_variance: float = Field(ge=0.0, le=1.0, description="Variance explained by this axis")
    positive_side: Optional[AxisSideDescription] = Field(
        default=None,
        description="Description of positive pole"
    )
    negative_side: Optional[AxisSideDescription] = Field(
        default=None,
        description="Description of negative pole"
    )
    positive_pole_fragments: List[str] = Field(
        default_factory=list,
        description="Evidence IDs at positive extreme"
    )
    negative_pole_fragments: List[str] = Field(
        default_factory=list,
        description="Evidence IDs at negative extreme"
    )


class DispersionEllipse(BaseModel):
    """Ellipse representing group position dispersion."""
    center_x: float = Field(description="X coordinate of ellipse center")
    center_y: float = Field(description="Y coordinate of ellipse center")
    radius_x: float = Field(ge=0.0, description="Semi-axis length along X")
    radius_y: float = Field(ge=0.0, description="Semi-axis length along Y")
    rotation: float = Field(default=0.0, description="Rotation angle in degrees")


class GroupPosition(BaseModel):
    """Position of a parliamentary group in the compass space."""
    group_id: str = Field(description="Parliamentary group name")
    position_x: float = Field(description="X coordinate (PC1)")
    position_y: float = Field(default=0.0, description="Y coordinate (PC2), 0 in 1D mode")
    dispersion: DispersionEllipse = Field(description="Dispersion ellipse")
    stats: Dict[str, Any] = Field(
        default_factory=dict,
        description="Statistics: n_fragments, confidence, etc."
    )
    core_evidence_ids: List[str] = Field(
        default_factory=list,
        description="Evidence IDs closest to group centroid"
    )


class CompassMetadata(BaseModel):
    """Metadata about the compass analysis."""
    query: str = Field(default="", description="Original query")
    dimensionality: int = Field(default=2, description="1 or 2 dimensions")
    explained_variance_ratio: List[float] = Field(
        default_factory=list,
        description="Variance explained by each PC"
    )
    total_variance_explained: float = Field(
        default=0.0,
        description="Total variance explained by selected PCs"
    )
    n_evidence: int = Field(default=0, description="Number of evidence fragments analyzed")
    is_stable: bool = Field(default=False, description="Whether analysis is statistically stable")
    warnings: List[str] = Field(
        default_factory=list,
        description="Warning messages about analysis quality"
    )


class CompassAnalysisResponse(BaseModel):
    """Complete response from compass analysis pipeline."""
    meta: CompassMetadata = Field(description="Analysis metadata")
    axes: Dict[str, AxisDefinition] = Field(
        default_factory=dict,
        description="Axis definitions ('x' and optionally 'y')"
    )
    groups: List[GroupPosition] = Field(
        default_factory=list,
        description="Positions of parliamentary groups"
    )
    scatter_sample: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Sample of individual evidence points for visualization"
    )


# Internal dataclasses for pipeline processing

@dataclass
class Fragment:
    """Internal representation of an evidence fragment for processing."""
    id: str
    group_id: str
    speaker_id: str
    embedding: List[float]
    text: str
    date: Optional[str] = None
    confidence: float = 1.0


@dataclass
class ProjectedFragment:
    """Fragment after projection to PCA space."""
    fragment_id: str
    group_id: str
    raw_coordinates: tuple  # (x, y) before scaling
    coordinates: tuple = (0.0, 0.0)  # (x, y) after scaling
    confidence: float = 0.0  # SCR (Subspace Contribution Ratio)
    is_outlier: bool = False
    text: str = ""


class CompassRefusalError(Exception):
    """Raised when compass analysis cannot produce reliable results."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")
