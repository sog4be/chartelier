"""Chart templates for visualization patterns.

Templates are organized by pattern ID (P01-P32) following the 3x3 matrix design:
- P01-P03: Single intent patterns
- P12-P32: Dual intent patterns combining Transition/Difference/Overview
"""

# Import templates from pattern-based folder structure
from .p01 import LineTemplate
from .p02 import BarTemplate
from .p03 import HistogramTemplate
from .p12 import MultiLineTemplate
from .p13 import FacetHistogramTemplate
from .p21 import GroupedBarTemplate
from .p23 import OverlayHistogramTemplate
from .p31 import SmallMultiplesTemplate
from .p32 import BoxPlotTemplate

__all__ = [
    "BarTemplate",
    "BoxPlotTemplate",
    "FacetHistogramTemplate",
    "GroupedBarTemplate",
    "HistogramTemplate",
    "LineTemplate",
    "MultiLineTemplate",
    "OverlayHistogramTemplate",
    "SmallMultiplesTemplate",
]
