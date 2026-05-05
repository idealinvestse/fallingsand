"""Sparse region optimization for conditional GPU dispatch."""

import numpy as np
from typing import List, Tuple


class SparseMask:
    """Tracks active regions for conditional dispatch."""

    def __init__(self, width: int, height: int):
        """Initialize sparse mask for given grid dimensions."""
        self.width = width
        self.height = height
        self.active_regions: List[Tuple[int, int, int, int]] = []
        self.sparse_enabled = False

    def update_mask(self, cells: np.ndarray) -> None:
        """Update mask based on non-air cells."""
        if not self.sparse_enabled:
            self.active_regions = [(0, 0, self.width, self.height)]
            return

        # Convert cells to 2D grid
        grid = cells.reshape((self.height, self.width))
        
        # Find non-air cells (type != 0)
        non_air_mask = grid != 0
        
        # If no non-air cells, use full grid
        if not np.any(non_air_mask):
            self.active_regions = [(0, 0, self.width, self.height)]
            return
        
        # Find bounding boxes of active regions using connected components
        # For simplicity, use a single bounding box around all active cells
        rows, cols = np.where(non_air_mask)
        if len(rows) == 0:
            self.active_regions = [(0, 0, self.width, self.height)]
            return
        
        min_y, max_y = rows.min(), rows.max()
        min_x, max_x = cols.min(), cols.max()
        
        # Expand by margin for edge effects
        margin = 8
        min_y = max(0, min_y - margin)
        max_y = min(self.height, max_y + margin + 1)
        min_x = max(0, min_x - margin)
        max_x = min(self.width, max_x + margin + 1)
        
        self.active_regions = [(min_x, min_y, max_x - min_x, max_y - min_y)]

    def get_dispatch_ranges(self) -> List[Tuple[int, int, int, int]]:
        """Return (x, y, w, h) for each active region."""
        if not self.sparse_enabled or not self.active_regions:
            return [(0, 0, self.width, self.height)]
        return self.active_regions

    def enable_sparse(self, enabled: bool) -> None:
        """Enable or disable sparse mode."""
        self.sparse_enabled = enabled
