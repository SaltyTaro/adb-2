# API Documentation

## Overview

The Advanced Dependency Intelligence Platform provides a comprehensive REST API for managing and analyzing project dependencies. The API allows you to programmatically interact with all features of the platform, including dependency analysis, impact scoring, and code adaptation.

## Authentication

All API requests (except for authentication endpoints) require a valid authentication token.

### Obtaining an Authentication Token

```
POST /api/v1/auth/token
```

**Request Body (form-data):**
```
username: string
password: string
```

**Response:**
```json
{
  "access_token": "string",
  "token_type": "bearer"
}
```

**Usage Example:**

```bash
curl -X POST http://localhost:8000/api/v1/auth/token \
  -d "username=youruser&password=yourpassword"
```

### Using the Token

Include the token in the Authorization header of all subsequent requests:

```
Authorization: Bearer {your_token}
```

## API Endpoints

### Projects

#### List Projects

```
GET /api/v1/projects/
```

Returns a list of all projects accessible to the authenticated user.

**Response:**
```json
[
  {
    "id": "uuid",
    "name": "string",
    "description": "string",
    "ecosystem": "string",
    "repository_url": "string",
    "owner_id": "uuid",
    "created_at": "datetime",
    "updated_at": "datetime",
    "dependency_count": 0,
    "analyses_count": 0,
    "risk_level": "string",
    "last_analysis": "datetime"
  }
]
```

#### Get Project

```
GET /api/v1/projects/{project_id}
```

Returns detailed information about a specific project.

**Response:**
```json
{
  "id": "uuid",
  "name": "string",
  "description": "string",
  "ecosystem": "string",
  "repository_url": "string",
  "owner_id": "uuid",
  "created_at": "datetime",
  "updated_at": "datetime",
  "dependency_count": 0,
  "analyses_count": 0,
  "risk_level": "string",
  "last_analysis": "datetime"
}
```

#### Create Project

```
POST /api/v1/projects/
```

Creates a new project.

**Request Body:**
```json
{
  "name": "string",
  "description": "string",
  "ecosystem": "string",
  "repository_url": "string"
}
```

**Response:**
```json
{
  "id": "uuid",
  "name": "string",
  "description": "string",
  "ecosystem": "string",
  "repository_url": "string",
  "owner_id": "uuid",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

#### Update Project

```
PUT /api/v1/projects/{project_id}
```

Updates an existing project.

**Request Body:**
```json
{
  "name": "string",
  "description": "string",
  "repository_url": "string"
}
```

**Response:**
```json
{
  "id": "uuid",
  "name": "string",
  "description": "string",
  "ecosystem": "string",
  "repository_url": "string",
  "owner_id": "uuid",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

#### Delete Project

```
DELETE /api/v1/projects/{project_id}
```

Deletes a project.

**Response:**
```json
{
  "success": true,
  "message": "Project deleted successfully"
}
```

#### Upload Project Files

```
POST /api/v1/projects/{project_id}/upload
```

Upload dependency files for analysis.

**Request Body (multipart/form-data):**
```
files: file(s)
```

**Response:**
```json
{
  "uploaded_files": [
    "string"
  ],
  "message": "string"
}
```

### Dependencies

#### List Dependencies

```
GET /api/v1/dependencies/
```

Returns a list of all dependencies.

**Query Parameters:**
- `ecosystem` (optional): Filter by ecosystem (e.g., "python", "nodejs")
- `page` (optional): Page number for pagination
- `limit` (optional): Results per page

**Response:**
```json
[
  {
    "id": "uuid",
    "name": "string",
    "ecosystem": "string",
    "latest_version": "string",
    "description": "string",
    "repository_url": "string",
    "homepage_url": "string",
    "health_score": 0.0,
    "is_deprecated": false,
    "created_at": "datetime",
    "updated_at": "datetime"
  }
]
```

#### Get Dependency

```
GET /api/v1/dependencies/{dependency_id}
```

Returns detailed information about a specific dependency.

**Response:**
```json
{
  "id": "uuid",
  "name": "string",
  "ecosystem": "string",
  "latest_version": "string",
  "description": "string",
  "repository_url": "string",
  "homepage_url": "string",
  "health_score": 0.0,
  "is_deprecated": false,
  "created_at": "datetime",
  "updated_at": "datetime",
  "metadata": {},
  "versions": []
}
```

#### Refresh Dependency

```
POST /api/v1/dependencies/{dependency_id}/refresh
```

Refreshes dependency information from external sources.

**Response:**
```json
{
  "id": "uuid",
  "name": "string",
  "ecosystem": "string",
  "latest_version": "string",
  "description": "string",
  "health_score": 0.0,
  "is_deprecated": false,
  "updated_at": "datetime"
}
```

#### Search Dependencies

```
GET /api/v1/dependencies/search/
```

Searches for dependencies based on a query string.

**Query Parameters:**
- `q`: Search query
- `ecosystem` (optional): Filter by ecosystem

**Response:**
```json
[
  {
    "id": "uuid",
    "name": "string",
    "ecosystem": "string",
    "latest_version": "string",
    "description": "string",
    "health_score": 0.0
  }
]
```

### Analyses

#### List Project Analyses

```
GET /api/v1/projects/{project_id}/analyses
```

Returns a list of all analyses for a specific project.

**Response:**
```json
[
  {
    "id": "uuid",
    "status": "string",
    "analysis_type": "string",
    "project_id": "uuid",
    "started_at": "datetime",
    "completed_at": "datetime",
    "created_at": "datetime",
    "updated_at": "datetime"
  }
]
```

#### Start Analysis

```
POST /api/v1/projects/{project_id}/analyze
```

Starts a new analysis for a specific project.

**Request Body:**
```json
{
  "analysis_type": "string",
  "config": {}
}
```

**Available Analysis Types:**
- `impact_scoring`: Calculate impact scores for dependencies
- `compatibility_prediction`: Predict compatibility issues
- `dependency_consolidation`: Identify duplicate dependencies
- `health_monitoring`: Monitor dependency health
- `license_compliance`: Check license compliance
- `performance_profiling`: Profile dependency performance

**Response:**
```json
{
  "id": "uuid",
  "status": "string",
  "analysis_type": "string",
  "project_id": "uuid",
  "started_at": "datetime",
  "created_at": "datetime"
}
```

#### Get Analysis

```
GET /api/v1/analyses/{analysis_id}
```

Returns detailed information about a specific analysis.

**Response:**
```json
{
  "id": "uuid",
  "status": "string",
  "analysis_type": "string",
  "project_id": "uuid",
  "started_at": "datetime",
  "completed_at": "datetime",
  "result": {},
  "error_message": "string",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

#### Get Analysis Details

```
GET /api/v1/analyses/{analysis_id}/details
```

Returns detailed results for a specific analysis.

**Response:**
```json
{
  "analysis_id": "uuid",
  "analysis_type": "string",
  "result_summary": {},
  "detailed_results": {}
}
```

### Recommendations

#### List Recommendations

```
GET /api/v1/projects/{project_id}/recommendations
```

Returns a list of all recommendations for a specific project.

**Response:**
```json
[
  {
    "id": "uuid",
    "title": "string",
    "description": "string",
    "recommendation_type": "string",
    "severity": "string",
    "impact": 0.0,
    "effort": 0.0,
    "dependency_name": "string",
    "from_version": "string",
    "to_version": "string",
    "created_at": "datetime",
    "updated_at": "datetime"
  }
]
```

#### Generate Recommendations

```
GET /api/v1/projects/{project_id}/generate-recommendations
```

Generates recommendations based on project analyses.

**Response:**
```json
{
  "message": "string",
  "count": 0,
  "recommendations": []
}
```

## Error Handling

The API uses standard HTTP status codes to indicate the success or failure of a request.

- `200 OK`: Request succeeded
- `400 Bad Request`: Invalid request parameters
- `401 Unauthorized`: Missing or invalid authentication
- `403 Forbidden`: Insufficient permissions
- `404 Not Found`: Resource not found
- `422 Unprocessable Entity`: Validation error
- `500 Internal Server Error`: Server error

Error responses include a JSON body with details:

```json
{
  "detail": "Error message"
}
```

## Rate Limiting

API requests are subject to rate limiting to ensure fair usage. Current limits are:

- 100 requests per minute per user
- 5 concurrent analyses per project

When a rate limit is exceeded, the API returns a `429 Too Many Requests` status code.

## API Key Management

API keys can be created and managed through the web interface or via the API:

```
POST /api/v1/auth/api-keys
```

**Request Body:**
```json
{
  "name": "string"
}
```

**Response:**
```json
{
  "id": "uuid",
  "name": "string",
  "api_key": "string",
  "created_at": "datetime",
  "expires_at": "datetime"
}
```

**Note:** The API key is only shown once at creation time. Store it securely.