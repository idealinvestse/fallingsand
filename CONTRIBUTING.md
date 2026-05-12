# Contributing to Falling Sand

Thank you for your interest in contributing to Falling Sand! This document provides guidelines and instructions for contributing to the project.

## Code of Conduct

Please be respectful and constructive in all interactions. See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) for details.

## Development Setup

### Prerequisites

- Python 3.11 or later
- Modern GPU with OpenGL 4.3+ support
- Git

### Setting Up the Development Environment

1. Clone the repository:
```bash
git clone https://github.com/idealinvestse/fallingsand.git
cd fallingsand
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements-dev.txt
```

4. Run the simulation:
```bash
python main.py
```

## Running Tests

Run the test suite:
```bash
pytest
```

Run tests with coverage:
```bash
pytest --cov=. --cov-report=html
```

## Code Style

Follow the existing code style:
- Use 4 spaces for indentation
- Follow PEP 8 guidelines
- Use type hints where appropriate
- Add docstrings to functions and classes

Run the linter:
```bash
ruff check .
```

Auto-fix linting issues:
```bash
ruff check --fix .
```

Run type checker:
```bash
mypy .
```

## Project Structure

- `core/`: Core configuration and constants
- `gpu/`: GPU pipeline, buffers, and compute passes
- `shaders/`: GLSL compute shaders
- `simulation/`: Simulation engine, materials, and state management
- `ui/`: User interface components (HUD, inspector, overlays)
- `tests/`: Unit tests and integration tests
- `docs/`: Documentation

## Submitting Changes

### Pull Request Process

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Make your changes
4. Run tests and ensure they pass
5. Commit your changes with clear messages
6. Push to your fork (`git push origin feature/my-feature`)
7. Create a pull request

### Pull Request Guidelines

- Use the [PR template](.github/pull_request_template.md)
- Link to related issues
- Describe your changes clearly
- Ensure all tests pass
- Update documentation if needed

## Adding New Materials

To add a new material:

1. Add the material definition to `simulation/materials_v6.yaml`
2. Add the material type constant to `shaders/common.glsl`
3. Update `NUM_TYPES` in `core/constants.py` if needed
4. Add material-specific logic to shaders if needed
5. Test the material in-game

## Adding New Shaders

To add a new compute shader:

1. Create the shader file in `shaders/`
2. Register the shader in `gpu/pass_graph.py`
3. Add resource bindings if needed
4. Update the shader registry in `shader_loader.py`
5. Test the shader with various materials

## Reporting Issues

Use the issue templates in `.github/ISSUE_TEMPLATE/`:
- `bug_report.md` for bugs
- `feature_request.md` for feature requests

Include:
- Steps to reproduce
- Expected vs actual behavior
- Environment details (OS, GPU, Python version)
- Screenshots if applicable

## Documentation

Documentation is in `docs/`:
- `ARCHITECTURE.md`: System architecture
- `GPU_PIPELINE.md`: GPU pipeline details
- `PERFORMANCE.md`: Performance guide
- `ELECTRICITY.md`: Electricity system
- `BIOLOGY.md`: Biology/ecology system
- `WEATHER.md`: Weather/atmospheric system
- `CHANGELOG.md`: Version history

Update documentation when making significant changes.

## Questions?

Feel free to open an issue with the "question" label for any questions about contributing.
