# Advanced Dependency Intelligence Platform

A modern, AI-powered platform for analyzing, managing, and optimizing project dependencies across multiple ecosystems.

## Overview

The Advanced Dependency Intelligence Platform helps developers and organizations understand and manage their project dependencies through advanced analytics, AI-powered recommendations, and comprehensive health monitoring.

### Key Features

- **Impact Scoring**: Understand the importance and risk profile of each dependency
- **Predictive Management**: AI-powered forecasting of compatibility issues and breaking changes
- **Dependency Consolidation**: Identify duplicate functionality and optimize dependency trees
- **Health Monitoring**: Track the vitality of open-source projects beyond just version numbers
- **License Compliance**: Track and analyze license dependencies throughout the project
- **Performance Profiling**: Analyze runtime and bundle size impacts of dependencies
- **Code Adaptation**: AI-assisted code transformations for version upgrades

## Architecture

The platform consists of:

- **Backend**: Python-based REST API built with FastAPI
- **Frontend**: React-based SPA (separate repository)
- **CLI**: Command-line interface for integration with CI/CD pipelines
- **AI Models**: Machine learning models for predictive analysis

## Getting Started

### Prerequisites

- Python 3.8+
- PostgreSQL 12+
- Node.js 14+ (for frontend)
- Docker and Docker Compose (optional)

### Installation

1. Clone this repository:

```bash
git clone https://github.com/yourusername/advanced-dependency-intelligence.git
cd advanced-dependency-intelligence
```

2. Set up a virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:

```bash
pip install -e .
```

4. Set up environment variables:

```bash
cp .env.example .env
# Edit .env with your database credentials and settings
```

5. Initialize the database:

```bash
python -m backend.core.db init_db
```

### Running with Docker

```bash
docker-compose up -d
```

### Running Locally

Start the backend:

```bash
uvicorn backend.main:app --reload
```

## API Documentation

Once running, API documentation is available at:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## CLI Usage

```bash
# Analyze a project
deptool analyze --path /path/to/project --ecosystem python

# Generate a report
deptool report --project-id abc-123 --format json

# Check for updates
deptool update --check --project-id abc-123
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Contributing

Please read CONTRIBUTING.md for details on our code of conduct and the process for submitting pull requests.