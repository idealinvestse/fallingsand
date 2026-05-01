import pytest
import numpy as np
from unittest.mock import Mock, MagicMock, patch
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def mock_pygame():
    """Mock pygame module and its components."""
    with patch('pygame.init') as mock_init, \
         patch('pygame.display.set_mode') as mock_set_mode, \
         patch('pygame.display.set_caption') as mock_set_caption, \
         patch('pygame.display.flip') as mock_flip, \
         patch('pygame.event.get') as mock_event_get, \
         patch('pygame.mouse.get_pressed') as mock_mouse_pressed, \
         patch('pygame.mouse.get_pos') as mock_mouse_pos, \
         patch('pygame.time.Clock') as mock_clock, \
         patch('pygame.quit') as mock_quit, \
         patch('pygame.font.SysFont') as mock_font:

        # Setup mock clock
        mock_clock_instance = Mock()
        mock_clock_instance.tick = Mock()
        mock_clock.return_value = mock_clock_instance

        # Setup mock event loop
        mock_event_get.return_value = []

        # Setup mock mouse
        mock_mouse_pressed.return_value = (False, False, False)
        mock_mouse_pos.return_value = (100, 100)

        # Setup mock font
        mock_font_instance = Mock()
        mock_font.return_value = mock_font_instance

        yield {
            'init': mock_init,
            'set_mode': mock_set_mode,
            'set_caption': mock_set_caption,
            'flip': mock_flip,
            'event_get': mock_event_get,
            'mouse_pressed': mock_mouse_pressed,
            'mouse_pos': mock_mouse_pos,
            'clock': mock_clock,
            'clock_instance': mock_clock_instance,
            'quit': mock_quit,
            'font': mock_font,
            'font_instance': mock_font_instance,
        }


@pytest.fixture
def mock_moderngl():
    """Mock moderngl module and its components."""
    with patch('moderngl.create_context') as mock_create_ctx:
        # Setup mock context
        mock_ctx = MagicMock()
        mock_create_ctx.return_value = mock_ctx

        # Setup mock buffers
        mock_buffer = MagicMock()
        mock_ctx.buffer = Mock(return_value=mock_buffer)

        # Setup mock compute shader
        mock_compute_shader = MagicMock()
        mock_ctx.compute_shader = Mock(return_value=mock_compute_shader)

        # Setup mock texture
        mock_texture = MagicMock()
        mock_ctx.texture = Mock(return_value=mock_texture)

        # Setup mock program
        mock_program = MagicMock()
        mock_ctx.program = Mock(return_value=mock_program)

        # Setup mock vertex array
        mock_vao = MagicMock()
        mock_ctx.vertex_array = Mock(return_value=mock_vao)

        yield {
            'create_context': mock_create_ctx,
            'context': mock_ctx,
            'buffer': mock_buffer,
            'compute_shader': mock_compute_shader,
            'texture': mock_texture,
            'program': mock_program,
            'vao': mock_vao,
        }


@pytest.fixture
def mock_grid_data():
    """Sample grid data for testing."""
    # Create a small 10x10 grid for testing
    grid = np.zeros(100, dtype=np.uint32)
    return grid


@pytest.fixture
def material_fixtures():
    """Fixture to access PARTICLES dict from main module."""
    # Import here to avoid import errors during fixture collection
    from main import PARTICLES
    return PARTICLES


@pytest.fixture
def temp_grid():
    """Temporary grid for isolated tests."""
    grid = np.zeros(64 * 64, dtype=np.uint32)  # 64x64 grid
    return grid


@pytest.fixture
def sample_cells():
    """Sample cell data with various material types."""
    from main import pack_cell, make_cell

    cells = {
        'air': make_cell(0),
        'sand': make_cell(1),
        'water': make_cell(2),
        'stone': make_cell(3),
        'fire': pack_cell(4, 220, 20, 0),
        'custom': pack_cell(5, 150, 10, 5),
    }
    return cells
