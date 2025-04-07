import os
import sys
import click
import json
import requests
import logging
import tempfile
import zipfile
from typing import Dict, List, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


@click.command()
@click.option("--path", "-p", required=True, help="Path to project directory")
@click.option("--ecosystem", "-e", help="Project ecosystem (python, nodejs)")
@click.option("--output", "-o", help="Output file for results")
@click.option("--analyze-type", "-t", default="all", 
              help="Analysis type (impact_scoring, compatibility_prediction, dependency_consolidation, "
                   "health_monitoring, license_compliance, performance_profiling, all)")
@click.option("--project-id", help="Project ID (if already exists)")
@click.option("--project-name", help="Project name (for new projects)")
@click.pass_context
def analyze(ctx, path, ecosystem, output, analyze_type, project_id, project_name):
    """
    Analyze a project's dependencies.
    
    This command performs analysis on a project's dependencies, providing insights
    into their impact, health, and compatibility.
    """
    api_url = ctx.obj.get("API_URL")
    api_key = ctx.obj.get("API_KEY")
    
    if not os.path.exists(path):
        logger.error(f"Project path not found: {path}")
        sys.exit(1)
    
    # Validate path is a directory
    if not os.path.isdir(path):
        logger.error(f"Path is not a directory: {path}")
        sys.exit(1)
    
    # Use directory name as project name if not specified
    if not project_name:
        project_name = os.path.basename(os.path.abspath(path))
    
    # Detect ecosystem if not specified
    if not ecosystem:
        ecosystem = detect_ecosystem(path)
        if not ecosystem:
            logger.error("Could not detect project ecosystem. Please specify with --ecosystem.")
            sys.exit(1)
        logger.info(f"Detected ecosystem: {ecosystem}")
    
    # Check if API key is provided for authentication
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    
    try:
        # Create or get project
        if not project_id:
            # Create new project
            project_data = {
                "name": project_name,
                "ecosystem": ecosystem,
                "description": f"Project at {path}"
            }
            
            response = requests.post(
                f"{api_url}/projects/",
                headers=headers,
                json=project_data
            )
            response.raise_for_status()
            
            project = response.json()
            project_id = project["id"]
            logger.info(f"Created project: {project_name} (ID: {project_id})")
        else:
            # Verify project exists
            response = requests.get(
                f"{api_url}/projects/{project_id}",
                headers=headers
            )
            response.raise_for_status()
            project = response.json()
            logger.info(f"Using existing project: {project['name']} (ID: {project_id})")
        
        # Upload project files for dependency analysis
        upload_files(api_url, headers, project_id, path, ecosystem)
        
        # Run requested analyses
        analysis_results = {}
        
        if analyze_type == "all":
            analysis_types = [
                "impact_scoring", 
                "compatibility_prediction",
                "dependency_consolidation", 
                "health_monitoring",
                "license_compliance", 
                "performance_profiling"
            ]
        else:
            analysis_types = [analyze_type]
        
        for analysis_type in analysis_types:
            logger.info(f"Running {analysis_type} analysis...")
            result = run_analysis(api_url, headers, project_id, analysis_type)
            analysis_results[analysis_type] = result
            
            # Wait for analysis to complete and get results
            if "id" in result:
                analysis_id = result["id"]
                complete_result = wait_for_analysis(api_url, headers, analysis_id)
                analysis_results[analysis_type] = complete_result
        
        # Save results if output file specified
        if output:
            with open(output, "w") as f:
                json.dump(analysis_results, f, indent=2)
            logger.info(f"Analysis results saved to {output}")
        
        # Print summary
        click.echo("\nAnalysis Summary:")
        for analysis_type, result in analysis_results.items():
            status = result.get("status", "unknown")
            if status == "completed":
                click.echo(f"  {analysis_type}: Completed successfully")
            else:
                click.echo(f"  {analysis_type}: {status}")
        
        return analysis_results
    
    except requests.exceptions.RequestException as e:
        logger.error(f"API request failed: {str(e)}")
        if hasattr(e, "response") and e.response is not None:
            if e.response.text:
                try:
                    error_data = e.response.json()
                    logger.error(f"Error details: {json.dumps(error_data)}")
                except:
                    logger.error(f"Error response: {e.response.text}")
        sys.exit(1)
    
    except Exception as e:
        logger.error(f"Error during analysis: {str(e)}")
        if ctx.obj.get("DEBUG"):
            import traceback
            traceback.print_exc()
        sys.exit(1)


def detect_ecosystem(path: str) -> Optional[str]:
    """
    Detect the project ecosystem based on files in the directory.
    
    Args:
        path: Path to project directory
        
    Returns:
        Detected ecosystem or None
    """
    # Check for Python ecosystem
    python_files = [
        "requirements.txt",
        "setup.py",
        "pyproject.toml",
        "Pipfile",
        "poetry.lock"
    ]
    
    # Check for Node.js ecosystem
    nodejs_files = [
        "package.json",
        "yarn.lock",
        "package-lock.json",
        "npm-shrinkwrap.json"
    ]
    
    # Check if any ecosystem files exist
    for py_file in python_files:
        if os.path.exists(os.path.join(path, py_file)):
            return "python"
    
    for js_file in nodejs_files:
        if os.path.exists(os.path.join(path, js_file)):
            return "nodejs"
    
    # If there are a lot of .py files, assume Python
    py_count = 0
    js_count = 0
    
    for root, _, files in os.walk(path):
        for file in files:
            if file.endswith(".py"):
                py_count += 1
            elif file.endswith((".js", ".jsx", ".ts", ".tsx")):
                js_count += 1
    
    if py_count > js_count and py_count > 5:
        return "python"
    elif js_count > py_count and js_count > 5:
        return "nodejs"
    
    # Could not determine ecosystem
    return None


def upload_files(api_url: str, headers: Dict[str, str], project_id: str, path: str, ecosystem: str) -> Dict[str, Any]:
    """
    Upload project files for dependency analysis.
    
    Args:
        api_url: API URL
        headers: Request headers
        project_id: Project ID
        path: Path to project directory
        ecosystem: Project ecosystem
        
    Returns:
        Upload response data
    """
    logger.info("Preparing project files for upload...")
    
    # Create a temporary zip file with relevant dependencies
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as temp_zip:
        temp_zip_path = temp_zip.name
    
    try:
        # Add relevant files based on ecosystem
        included_files = []
        
        with zipfile.ZipFile(temp_zip_path, "w") as zipf:
            if ecosystem == "python":
                # Add Python dependency files
                dependency_files = [
                    "requirements.txt",
                    "setup.py",
                    "pyproject.toml",
                    "Pipfile",
                    "Pipfile.lock",
                    "poetry.lock"
                ]
                
                for file in dependency_files:
                    file_path = os.path.join(path, file)
                    if os.path.exists(file_path):
                        zipf.write(file_path, arcname=file)
                        included_files.append(file)
                
                # Also include requirements subdirectory if it exists
                req_dir = os.path.join(path, "requirements")
                if os.path.exists(req_dir) and os.path.isdir(req_dir):
                    for file in os.listdir(req_dir):
                        if file.endswith(".txt"):
                            file_path = os.path.join(req_dir, file)
                            zipf.write(file_path, arcname=os.path.join("requirements", file))
                            included_files.append(os.path.join("requirements", file))
            
            elif ecosystem == "nodejs":
                # Add Node.js dependency files
                dependency_files = [
                    "package.json",
                    "package-lock.json",
                    "yarn.lock",
                    "npm-shrinkwrap.json"
                ]
                
                for file in dependency_files:
                    file_path = os.path.join(path, file)
                    if os.path.exists(file_path):
                        zipf.write(file_path, arcname=file)
                        included_files.append(file)
        
        if not included_files:
            logger.warning(f"No dependency files found for {ecosystem} ecosystem")
            return {"message": "No dependency files found"}
        
        logger.info(f"Uploading files: {', '.join(included_files)}")
        
        # Upload the zip file
        with open(temp_zip_path, "rb") as zip_file:
            upload_headers = headers.copy()
            # Remove content-type for multipart upload
            if "Content-Type" in upload_headers:
                del upload_headers["Content-Type"]
                
            files = {
                "files": ("project.zip", zip_file, "application/zip")
            }
            
            response = requests.post(
                f"{api_url}/projects/{project_id}/upload",
                headers=upload_headers,
                files=files
            )
            response.raise_for_status()
            
            result = response.json()
            logger.info(f"Upload successful: {result.get('message', '')}")
            return result
    
    finally:
        # Clean up the temporary file
        try:
            os.unlink(temp_zip_path)
        except:
            pass


def run_analysis(api_url: str, headers: Dict[str, str], project_id: str, analysis_type: str) -> Dict[str, Any]:
    """
    Run a specific analysis on a project.
    
    Args:
        api_url: API URL
        headers: Request headers
        project_id: Project ID
        analysis_type: Type of analysis to run
        
    Returns:
        Analysis response data
    """
    analysis_data = {
        "analysis_type": analysis_type
    }
    
    # Add specific configuration based on analysis type
    if analysis_type == "compatibility_prediction":
        analysis_data["config"] = {"time_horizon": 180}  # 6 months
    elif analysis_type == "performance_profiling":
        analysis_data["config"] = {"profile_type": "bundle_size"}
    elif analysis_type == "license_compliance":
        analysis_data["config"] = {"target_license": "mit"}
    
    response = requests.post(
        f"{api_url}/projects/{project_id}/analyze",
        headers=headers,
        json=analysis_data
    )
    response.raise_for_status()
    
    result = response.json()
    logger.info(f"Started {analysis_type} analysis (ID: {result.get('id', 'unknown')})")
    return result


def wait_for_analysis(api_url: str, headers: Dict[str, str], analysis_id: str) -> Dict[str, Any]:
    """
    Wait for analysis to complete and get results.
    
    Args:
        api_url: API URL
        headers: Request headers
        analysis_id: Analysis ID
        
    Returns:
        Analysis result data
    """
    import time
    
    max_retries = 60  # 5 minutes
    retry_count = 0
    
    while retry_count < max_retries:
        response = requests.get(
            f"{api_url}/analyses/{analysis_id}",
            headers=headers
        )
        response.raise_for_status()
        
        result = response.json()
        status = result.get("status")
        
        if status == "completed":
            logger.info(f"Analysis {analysis_id} completed successfully")
            
            # Get detailed results
            detail_response = requests.get(
                f"{api_url}/analyses/{analysis_id}/details",
                headers=headers
            )
            
            if detail_response.status_code == 200:
                detailed_result = detail_response.json()
                result["detailed_results"] = detailed_result
                logger.info(f"Retrieved detailed results for analysis {analysis_id}")
            
            return result
            
        elif status == "failed":
            logger.error(f"Analysis {analysis_id} failed: {result.get('error_message', 'Unknown error')}")
            return result
            
        logger.info(f"Analysis {analysis_id} status: {status}. Waiting...")
        retry_count += 1
        time.sleep(5)
    
    logger.warning(f"Analysis {analysis_id} is taking longer than expected, continuing without waiting")
    return {"id": analysis_id, "status": "timeout", "message": "Analysis is taking longer than expected"}


if __name__ == "__main__":
    # This allows the command to be run directly for testing
    analyze(obj={})