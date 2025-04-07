import os
import sys
import click
import json
import requests
import logging
import subprocess
from typing import Dict, List, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


@click.command()
@click.option("--project-id", "-p", required=True, help="Project ID")
@click.option("--dependency", "-d", help="Specific dependency to update")
@click.option("--target-version", "-v", help="Target version to update to")
@click.option("--check", is_flag=True, help="Check for updates without updating")
@click.option("--path", help="Path to project directory for applying updates")
@click.option("--transform-code", is_flag=True, help="Apply code transformations for breaking changes")
@click.option("--dry-run", is_flag=True, help="Show proposed changes without applying them")
@click.option("--all-dependencies", is_flag=True, help="Update all dependencies")
@click.option("--output", help="Output file for update plan")
@click.pass_context
def update(ctx, project_id, dependency, target_version, check, path, transform_code, dry_run, all_dependencies, output):
    """
    Check for dependency updates or upgrade dependencies.
    
    This command checks for available updates, scores their compatibility,
    and can optionally apply updates with code transformations.
    """
    api_url = ctx.obj.get("API_URL")
    api_key = ctx.obj.get("API_KEY")
    
    # Set up headers for API requests
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    
    try:
        # Get project information
        project = get_project(api_url, headers, project_id)
        
        # Get project dependencies
        dependencies = get_project_dependencies(api_url, headers, project_id)
        
        if dependency and dependency not in [dep["name"] for dep in dependencies]:
            logger.error(f"Dependency '{dependency}' not found in project")
            sys.exit(1)
        
        if check:
            # Only check for available updates
            update_checks = check_for_updates(api_url, headers, project_id, dependencies, dependency)
            
            if output:
                with open(output, "w") as f:
                    json.dump(update_checks, f, indent=2)
                logger.info(f"Update check results saved to {output}")
            else:
                display_update_checks(update_checks)
                
            return update_checks
        else:
            # Perform updates
            if not path:
                logger.error("Project path is required for performing updates")
                sys.exit(1)
                
            if not os.path.isdir(path):
                logger.error(f"Project path is not a directory: {path}")
                sys.exit(1)
            
            # Generate update plan
            update_plan = generate_update_plan(
                api_url, headers, project_id, dependencies, 
                dependency, target_version, all_dependencies
            )
            
            if output:
                with open(output, "w") as f:
                    json.dump(update_plan, f, indent=2)
                logger.info(f"Update plan saved to {output}")
            
            # Display the update plan
            display_update_plan(update_plan)
            
            if dry_run:
                logger.info("Dry run - no changes applied")
                return update_plan
            
            # Confirm update
            if not click.confirm("Do you want to apply these updates?"):
                logger.info("Update cancelled")
                return update_plan
            
            # Apply updates
            update_results = apply_updates(
                api_url, headers, project_id, update_plan, 
                path, transform_code
            )
            
            logger.info("Updates applied successfully")
            
            return update_results
    
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
        logger.error(f"Error during update: {str(e)}")
        if ctx.obj.get("DEBUG"):
            import traceback
            traceback.print_exc()
        sys.exit(1)


def get_project(api_url: str, headers: Dict[str, str], project_id: str) -> Dict[str, Any]:
    """
    Get project information from the API.
    
    Args:
        api_url: API URL
        headers: Request headers
        project_id: Project ID
        
    Returns:
        Project data
    """
    response = requests.get(
        f"{api_url}/projects/{project_id}",
        headers=headers
    )
    response.raise_for_status()
    
    return response.json()


def get_project_dependencies(api_url: str, headers: Dict[str, str], project_id: str) -> List[Dict[str, Any]]:
    """
    Get project dependencies from the API.
    
    Args:
        api_url: API URL
        headers: Request headers
        project_id: Project ID
        
    Returns:
        List of dependency data
    """
    response = requests.get(
        f"{api_url}/projects/{project_id}/dependencies",
        headers=headers
    )
    response.raise_for_status()
    
    return response.json()


def check_for_updates(
    api_url: str, 
    headers: Dict[str, str], 
    project_id: str, 
    dependencies: List[Dict[str, Any]],
    specific_dependency: Optional[str] = None
) -> Dict[str, Any]:
    """
    Check for available updates for dependencies.
    
    Args:
        api_url: API URL
        headers: Request headers
        project_id: Project ID
        dependencies: List of dependency data
        specific_dependency: Name of a specific dependency to check
        
    Returns:
        Update check results
    """
    logger.info("Checking for available updates...")
    
    result = {
        "project_id": project_id,
        "check_time": None,
        "dependencies": []
    }
    
    # Filter dependencies if a specific one is specified
    if specific_dependency:
        dependencies = [dep for dep in dependencies if dep["name"] == specific_dependency]
    
    # For each dependency, check for updates
    for dep in dependencies:
        dep_id = dep.get("id")
        dep_name = dep.get("name")
        current_version = dep.get("latest_version", "").replace("v", "")
        
        # Get dependency info
        response = requests.get(
            f"{api_url}/dependencies/{dep_id}",
            headers=headers
        )
        
        if response.status_code != 200:
            logger.warning(f"Could not get info for dependency {dep_name}")
            continue
            
        dep_info = response.json()
        available_versions = []
        
        # Find available versions
        for version in dep_info.get("versions", []):
            version_str = version.get("version", "").replace("v", "")
            
            if version_str and version_str != current_version:
                # Simple version comparison for sorting
                is_newer = is_version_newer(version_str, current_version)
                
                if is_newer:
                    published_at = version.get("published_at")
                    
                    available_versions.append({
                        "version": version_str,
                        "published_at": published_at,
                        "is_newer": is_newer
                    })
        
        # Sort versions by publish date (most recent first)
        available_versions.sort(
            key=lambda x: x.get("published_at", ""), 
            reverse=True
        )
        
        # Get compatibility scores for top versions
        latest_versions = available_versions[:3]  # Top 3 most recent
        compatibility_scores = []
        
        for version_info in latest_versions:
            version = version_info["version"]
            
            # Use predictive management to score compatibility
            compat_data = {
                "analysis_type": "compatibility_prediction",
                "config": {
                    "dependency": dep_name,
                    "current_version": current_version,
                    "target_version": version
                }
            }
            
            response = requests.post(
                f"{api_url}/projects/{project_id}/analyze",
                headers=headers,
                json=compat_data
            )
            
            if response.status_code == 200:
                analysis = response.json()
                analysis_id = analysis.get("id")
                
                # Wait for analysis to complete (simplified)
                max_retries = 10
                retry_count = 0
                
                while retry_count < max_retries:
                    response = requests.get(
                        f"{api_url}/analyses/{analysis_id}",
                        headers=headers
                    )
                    
                    if response.status_code == 200:
                        analysis_result = response.json()
                        if analysis_result.get("status") == "completed":
                            result_data = analysis_result.get("result", {})
                            
                            compatibility_scores.append({
                                "version": version,
                                "score": result_data.get("compatibility_score", 0.5),
                                "analysis_id": analysis_id
                            })
                            break
                    
                    retry_count += 1
                    import time
                    time.sleep(2)
        
        # Prepare update information for this dependency
        update_info = {
            "name": dep_name,
            "current_version": current_version,
            "ecosystem": dep.get("ecosystem"),
            "available_versions": available_versions,
            "compatibility_scores": compatibility_scores,
            "recommended_update": None
        }
        
        # Find the recommended update version
        if compatibility_scores:
            # Prefer versions with higher compatibility scores
            recommended = sorted(
                compatibility_scores,
                key=lambda x: (x.get("score", 0), x.get("version", "")),
                reverse=True
            )[0]
            
            update_info["recommended_update"] = {
                "version": recommended["version"],
                "compatibility_score": recommended["score"],
                "analysis_id": recommended["analysis_id"]
            }
        
        result["dependencies"].append(update_info)
    
    return result


def generate_update_plan(
    api_url: str, 
    headers: Dict[str, str], 
    project_id: str, 
    dependencies: List[Dict[str, Any]],
    specific_dependency: Optional[str] = None,
    target_version: Optional[str] = None,
    all_dependencies: bool = False
) -> Dict[str, Any]:
    """
    Generate a plan for updating dependencies.
    
    Args:
        api_url: API URL
        headers: Request headers
        project_id: Project ID
        dependencies: List of dependency data
        specific_dependency: Name of a specific dependency to update
        target_version: Target version to update to
        all_dependencies: Whether to update all dependencies
        
    Returns:
        Update plan
    """
    logger.info("Generating update plan...")
    
    # First get update check results
    update_checks = check_for_updates(
        api_url, headers, project_id, 
        dependencies, specific_dependency
    )
    
    plan = {
        "project_id": project_id,
        "plan_time": None,
        "dependencies_to_update": []
    }
    
    # Plan updates based on check results
    for dep_info in update_checks["dependencies"]:
        dep_name = dep_info["name"]
        current_version = dep_info["current_version"]
        
        # Determine target version based on inputs
        version_to_use = None
        compatibility_score = 0
        analysis_id = None
        
        if specific_dependency == dep_name and target_version:
            # Use specified target version
            version_to_use = target_version
            
            # Find compatibility score if available
            for score_info in dep_info.get("compatibility_scores", []):
                if score_info["version"] == target_version:
                    compatibility_score = score_info["score"]
                    analysis_id = score_info["analysis_id"]
                    break
        
        elif dep_info.get("recommended_update"):
            # Use recommended update
            recommended = dep_info["recommended_update"]
            version_to_use = recommended["version"]
            compatibility_score = recommended["compatibility_score"]
            analysis_id = recommended["analysis_id"]
        
        else:
            # No update available or recommended
            continue
        
        # Only include if it's the specific dependency, all_dependencies is set,
        # or it's a recommended update with good compatibility
        if (specific_dependency == dep_name or 
                all_dependencies or 
                (compatibility_score >= 0.7 and not specific_dependency)):
            
            # Get compatibility details for code transformation
            compatibility_details = {}
            if analysis_id:
                response = requests.get(
                    f"{api_url}/analyses/{analysis_id}/details",
                    headers=headers
                )
                
                if response.status_code == 200:
                    compatibility_details = response.json()
            
            plan["dependencies_to_update"].append({
                "name": dep_name,
                "ecosystem": dep_info["ecosystem"],
                "current_version": current_version,
                "target_version": version_to_use,
                "compatibility_score": compatibility_score,
                "breaking_changes": compatibility_details.get("breaking_changes", []),
                "compatibility_details": compatibility_details
            })
    
    return plan


def apply_updates(
    api_url: str, 
    headers: Dict[str, str], 
    project_id: str, 
    update_plan: Dict[str, Any],
    project_path: str,
    transform_code: bool
) -> Dict[str, Any]:
    """
    Apply dependency updates to a project.
    
    Args:
        api_url: API URL
        headers: Request headers
        project_id: Project ID
        update_plan: Update plan
        project_path: Path to project directory
        transform_code: Whether to apply code transformations
        
    Returns:
        Update results
    """
    logger.info("Applying updates...")
    
    results = {
        "project_id": project_id,
        "updated_dependencies": [],
        "code_transformations": [],
        "errors": []
    }
    
    # Group updates by ecosystem for batched updating
    updates_by_ecosystem = {}
    for dep in update_plan["dependencies_to_update"]:
        ecosystem = dep["ecosystem"]
        if ecosystem not in updates_by_ecosystem:
            updates_by_ecosystem[ecosystem] = []
        updates_by_ecosystem[ecosystem].append(dep)
    
    # Apply updates for each ecosystem
    for ecosystem, deps in updates_by_ecosystem.items():
        if ecosystem == "python":
            # Update Python dependencies
            python_results = update_python_dependencies(deps, project_path)
            results["updated_dependencies"].extend(python_results)
        
        elif ecosystem == "nodejs":
            # Update Node.js dependencies
            nodejs_results = update_nodejs_dependencies(deps, project_path)
            results["updated_dependencies"].extend(nodejs_results)
    
    # Apply code transformations if requested
    if transform_code:
        for dep in update_plan["dependencies_to_update"]:
            # Only transform if there are breaking changes
            if dep.get("breaking_changes"):
                logger.info(f"Applying code transformations for {dep['name']}...")
                
                transformation_results = transform_code_for_dependency(
                    api_url, headers, project_id, dep, project_path
                )
                
                results["code_transformations"].extend(transformation_results)
    
    return results


def update_python_dependencies(deps: List[Dict[str, Any]], project_path: str) -> List[Dict[str, Any]]:
    """
    Update Python dependencies using pip.
    
    Args:
        deps: List of dependencies to update
        project_path: Path to project directory
        
    Returns:
        Update results
    """
    results = []
    
    # Check for requirements.txt or other Python dependency files
    requirements_file = None
    for file_name in ["requirements.txt", "requirements-dev.txt", "requirements/base.txt"]:
        file_path = os.path.join(project_path, file_name)
        if os.path.exists(file_path):
            requirements_file = file_path
            break
    
    # Update each dependency
    for dep in deps:
        dep_name = dep["name"]
        target_version = dep["target_version"]
        
        logger.info(f"Updating {dep_name} to version {target_version}...")
        
        result = {
            "name": dep_name,
            "from_version": dep["current_version"],
            "to_version": target_version,
            "success": False,
            "modified_files": []
        }
        
        try:
            # Update pinned versions in requirements files
            if requirements_file:
                updated_files = update_requirements_file(
                    requirements_file, dep_name, target_version
                )
                result["modified_files"].extend(updated_files)
                
                # Check other potential requirement files in the project
                req_dir = os.path.join(project_path, "requirements")
                if os.path.isdir(req_dir):
                    for file_name in os.listdir(req_dir):
                        if file_name.endswith(".txt"):
                            req_file = os.path.join(req_dir, file_name)
                            updated = update_requirements_file(
                                req_file, dep_name, target_version
                            )
                            result["modified_files"].extend(updated)
            
            # Update setup.py if it exists
            setup_py = os.path.join(project_path, "setup.py")
            if os.path.exists(setup_py):
                updated = update_setup_py(setup_py, dep_name, target_version)
                if updated:
                    result["modified_files"].append(setup_py)
            
            # Update pyproject.toml if it exists
            pyproject = os.path.join(project_path, "pyproject.toml")
            if os.path.exists(pyproject):
                updated = update_pyproject_toml(pyproject, dep_name, target_version)
                if updated:
                    result["modified_files"].append(pyproject)
            
            # Install the new version using pip
            cmd = ["pip", "install", f"{dep_name}=={target_version}"]
            
            # Check if a virtual environment is active
            if "VIRTUAL_ENV" in os.environ:
                proc = subprocess.run(cmd, check=True, capture_output=True, text=True)
                result["output"] = proc.stdout
                result["success"] = True
            else:
                logger.warning("No active virtual environment detected, skipping pip install")
                # Still consider it successful if we updated the files
                result["success"] = bool(result["modified_files"])
        
        except subprocess.CalledProcessError as e:
            logger.error(f"Error updating {dep_name}: {e.stderr}")
            result["error"] = e.stderr
        
        except Exception as e:
            logger.error(f"Error updating {dep_name}: {str(e)}")
            result["error"] = str(e)
        
        results.append(result)
    
    return results


def update_nodejs_dependencies(deps: List[Dict[str, Any]], project_path: str) -> List[Dict[str, Any]]:
    """
    Update Node.js dependencies using npm or yarn.
    
    Args:
        deps: List of dependencies to update
        project_path: Path to project directory
        
    Returns:
        Update results
    """
    results = []
    
    # Determine package manager (npm or yarn)
    use_yarn = os.path.exists(os.path.join(project_path, "yarn.lock"))
    
    # Update each dependency
    for dep in deps:
        dep_name = dep["name"]
        target_version = dep["target_version"]
        
        logger.info(f"Updating {dep_name} to version {target_version}...")
        
        result = {
            "name": dep_name,
            "from_version": dep["current_version"],
            "to_version": target_version,
            "success": False,
            "modified_files": []
        }
        
        try:
            # Update package.json
            package_json = os.path.join(project_path, "package.json")
            if os.path.exists(package_json):
                updated = update_package_json(package_json, dep_name, target_version)
                if updated:
                    result["modified_files"].append(package_json)
            
            # Install the new version using npm or yarn
            if use_yarn:
                cmd = ["yarn", "add", f"{dep_name}@{target_version}"]
            else:
                cmd = ["npm", "install", f"{dep_name}@{target_version}", "--save"]
            
            # Run in the project directory
            proc = subprocess.run(
                cmd, 
                cwd=project_path,
                check=True, 
                capture_output=True, 
                text=True
            )
            
            result["output"] = proc.stdout
            result["success"] = True
            
            # Add lock files to modified files
            if use_yarn:
                result["modified_files"].append(os.path.join(project_path, "yarn.lock"))
            else:
                result["modified_files"].append(os.path.join(project_path, "package-lock.json"))
        
        except subprocess.CalledProcessError as e:
            logger.error(f"Error updating {dep_name}: {e.stderr}")
            result["error"] = e.stderr
        
        except Exception as e:
            logger.error(f"Error updating {dep_name}: {str(e)}")
            result["error"] = str(e)
        
        results.append(result)
    
    return results


def transform_code_for_dependency(
    api_url: str, 
    headers: Dict[str, str], 
    project_id: str, 
    dep: Dict[str, Any],
    project_path: str
) -> List[Dict[str, Any]]:
    """
    Apply code transformations for a dependency update.
    
    Args:
        api_url: API URL
        headers: Request headers
        project_id: Project ID
        dep: Dependency update information
        project_path: Path to project directory
        
    Returns:
        Code transformation results
    """
    results = []
    
    try:
        # Find all files that might use this dependency
        ecosystem = dep["ecosystem"]
        dep_name = dep["name"]
        
        if ecosystem == "python":
            file_extensions = [".py"]
        elif ecosystem == "nodejs":
            file_extensions = [".js", ".jsx", ".ts", ".tsx"]
        else:
            logger.warning(f"Unsupported ecosystem for code transformation: {ecosystem}")
            return results
        
        # Find relevant files
        files_to_transform = find_files_using_dependency(
            project_path, file_extensions, dep_name
        )
        
        logger.info(f"Found {len(files_to_transform)} files potentially using {dep_name}")
        
        # For each file, apply transformations
        for file_path in files_to_transform:
            rel_path = os.path.relpath(file_path, project_path)
            logger.info(f"Transforming {rel_path}...")
            
            # Read the file
            with open(file_path, "r") as f:
                original_code = f.read()
            
            # Use code adaptation service to transform the code
            data = {
                "analysis_type": "code_transformation",
                "config": {
                    "file_path": rel_path,
                    "dependency": dep_name,
                    "current_version": dep["current_version"],
                    "target_version": dep["target_version"],
                    "ecosystem": ecosystem,
                    "transformation_type": "auto"
                }
            }
            
            response = requests.post(
                f"{api_url}/projects/{project_id}/analyze",
                headers=headers,
                json=data
            )
            
            if response.status_code != 200:
                logger.warning(f"Failed to start transformation for {rel_path}")
                continue
                
            analysis = response.json()
            analysis_id = analysis.get("id")
            
            # Wait for transformation to complete
            max_retries = 20
            retry_count = 0
            
            while retry_count < max_retries:
                response = requests.get(
                    f"{api_url}/analyses/{analysis_id}",
                    headers=headers
                )
                
                if response.status_code == 200:
                    analysis_result = response.json()
                    if analysis_result.get("status") == "completed":
                        # Get transformation details
                        detail_response = requests.get(
                            f"{api_url}/analyses/{analysis_id}/details",
                            headers=headers
                        )
                        
                        if detail_response.status_code == 200:
                            details = detail_response.json()
                            
                            # If the code was transformed, update the file
                            if details.get("has_changes"):
                                transformed_code = details.get("transformed_code")
                                
                                # Write the transformed code
                                with open(file_path, "w") as f:
                                    f.write(transformed_code)
                                
                                results.append({
                                    "file": rel_path,
                                    "has_changes": True,
                                    "confidence": details.get("confidence", 0.5),
                                    "diff": details.get("diff", "")
                                })
                            else:
                                results.append({
                                    "file": rel_path,
                                    "has_changes": False
                                })
                            
                            break
                    
                    elif analysis_result.get("status") == "failed":
                        logger.warning(f"Transformation failed for {rel_path}")
                        break
                
                retry_count += 1
                import time
                time.sleep(3)
    
    except Exception as e:
        logger.error(f"Error applying code transformations: {str(e)}")
    
    return results


def find_files_using_dependency(
    project_path: str, 
    file_extensions: List[str],
    dependency_name: str
) -> List[str]:
    """
    Find files that might be using a dependency.
    
    Args:
        project_path: Path to project directory
        file_extensions: List of file extensions to search
        dependency_name: Name of the dependency
        
    Returns:
        List of file paths
    """
    matching_files = []
    
    # Directories to exclude
    exclude_dirs = ["node_modules", "venv", "env", ".git", "__pycache__", ".venv"]
    
    for root, dirs, files in os.walk(project_path):
        # Skip excluded directories
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        
        for file in files:
            if any(file.endswith(ext) for ext in file_extensions):
                file_path = os.path.join(root, file)
                
                # Quick check if the file contains the dependency name
                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                        
                    # Simple string search for the dependency name
                    if dependency_name in content:
                        matching_files.append(file_path)
                except:
                    # Skip files that can't be read
                    pass
    
    return matching_files


def update_requirements_file(file_path: str, dep_name: str, target_version: str) -> List[str]:
    """
    Update a Python requirements file with the new version.
    
    Args:
        file_path: Path to requirements file
        dep_name: Dependency name
        target_version: Target version
        
    Returns:
        List of updated file paths
    """
    updated_files = []
    
    try:
        with open(file_path, "r") as f:
            lines = f.readlines()
        
        updated_lines = []
        modified = False
        
        for line in lines:
            line_lower = line.lower().strip()
            if line_lower.startswith(dep_name.lower()) or \
               line_lower.startswith(f"-e {dep_name.lower()}") or \
               line_lower.startswith(f"--editable {dep_name.lower()}"):
                
                # Replace version specifier
                parts = line.split("#", 1)  # Preserve comments
                req_part = parts[0]
                comment_part = f"#{parts[1]}" if len(parts) > 1 else ""
                
                # Replace version specifier
                new_req = re.sub(
                    r"([<>=~!]|==).*?(\s|$|#)", 
                    f"=={target_version} ", 
                    req_part
                )
                
                updated_lines.append(f"{new_req}{comment_part}")
                modified = True
            else:
                updated_lines.append(line)
        
        if modified:
            with open(file_path, "w") as f:
                f.writelines(updated_lines)
                
            updated_files.append(file_path)
    
    except Exception as e:
        logger.error(f"Error updating requirements file {file_path}: {str(e)}")
    
    return updated_files


def update_setup_py(file_path: str, dep_name: str, target_version: str) -> bool:
    """
    Update a Python setup.py file with the new version.
    
    Args:
        file_path: Path to setup.py file
        dep_name: Dependency name
        target_version: Target version
        
    Returns:
        Whether the file was updated
    """
    try:
        with open(file_path, "r") as f:
            content = f.read()
        
        # Look for dependency in install_requires or extras_require
        dep_pattern = f"['\"]({re.escape(dep_name)})[<>=~!]*[^'\"]*['\"]"
        
        # Replace with exact version
        new_content = re.sub(
            dep_pattern,
            f"'\\1=={target_version}'",
            content
        )
        
        if new_content != content:
            with open(file_path, "w") as f:
                f.write(new_content)
                
            return True
    
    except Exception as e:
        logger.error(f"Error updating setup.py {file_path}: {str(e)}")
    
    return False


def update_pyproject_toml(file_path: str, dep_name: str, target_version: str) -> bool:
    """
    Update a Python pyproject.toml file with the new version.
    
    Args:
        file_path: Path to pyproject.toml file
        dep_name: Dependency name
        target_version: Target version
        
    Returns:
        Whether the file was updated
    """
    try:
        with open(file_path, "r") as f:
            content = f.read()
        
        # Look for dependency in dependencies sections
        dep_patterns = [
            f"({re.escape(dep_name)})[\\s]*=[\\s]*[\"'].*?[\"']",  # poetry style
            f"[\"']({re.escape(dep_name)})[<>=~!]*[^\"']*[\"']"  # requirements style
        ]
        
        updated_content = content
        for pattern in dep_patterns:
            # Replace with exact version for poetry style
            updated_content = re.sub(
                pattern,
                f"\\1 = \"{target_version}\"",
                updated_content
            )
        
        if updated_content != content:
            with open(file_path, "w") as f:
                f.write(updated_content)
                
            return True
    
    except Exception as e:
        logger.error(f"Error updating pyproject.toml {file_path}: {str(e)}")
    
    return False


def update_package_json(file_path: str, dep_name: str, target_version: str) -> bool:
    """
    Update a Node.js package.json file with the new version.
    
    Args:
        file_path: Path to package.json file
        dep_name: Dependency name
        target_version: Target version
        
    Returns:
        Whether the file was updated
    """
    try:
        with open(file_path, "r") as f:
            data = json.load(f)
        
        modified = False
        
        # Update in dependencies
        if "dependencies" in data and dep_name in data["dependencies"]:
            data["dependencies"][dep_name] = "^" + target_version
            modified = True
        
        # Update in devDependencies
        if "devDependencies" in data and dep_name in data["devDependencies"]:
            data["devDependencies"][dep_name] = "^" + target_version
            modified = True
        
        # Update in peerDependencies
        if "peerDependencies" in data and dep_name in data["peerDependencies"]:
            data["peerDependencies"][dep_name] = "^" + target_version
            modified = True
        
        if modified:
            with open(file_path, "w") as f:
                json.dump(data, f, indent=2)
                
            return True
    
    except Exception as e:
        logger.error(f"Error updating package.json {file_path}: {str(e)}")
    
    return False


def is_version_newer(version1: str, version2: str) -> bool:
    """
    Check if version1 is newer than version2.
    
    Args:
        version1: First version
        version2: Second version
        
    Returns:
        Whether version1 is newer than version2
    """
    try:
        # Simple implementation - split by dots and compare components
        v1_parts = [int(p) for p in version1.split(".")]
        v2_parts = [int(p) for p in version2.split(".")]
        
        # Make sure both lists have the same length
        while len(v1_parts) < len(v2_parts):
            v1_parts.append(0)
        while len(v2_parts) < len(v1_parts):
            v2_parts.append(0)
        
        # Compare each component
        for i in range(len(v1_parts)):
            if v1_parts[i] > v2_parts[i]:
                return True
            elif v1_parts[i] < v2_parts[i]:
                return False
        
        # If we get here, versions are equal
        return False
    
    except (ValueError, IndexError):
        # If parsing fails, fall back to string comparison
        return version1 > version2


def display_update_checks(update_checks: Dict[str, Any]) -> None:
    """
    Display update check results in a user-friendly format.
    
    Args:
        update_checks: Update check results
    """
    click.echo("\nAvailable Updates:")
    click.echo("-" * 80)
    
    if not update_checks.get("dependencies"):
        click.echo("No dependencies found for update checking.")
        return
    
    for dep_info in update_checks["dependencies"]:
        dep_name = dep_info["name"]
        current_version = dep_info["current_version"]
        
        click.echo(f"\n{dep_name} (current: {current_version})")
        
        available_versions = dep_info.get("available_versions", [])
        if not available_versions:
            click.echo("  No newer versions available")
            continue
        
        # Display available versions
        click.echo("  Available versions:")
        for i, version in enumerate(available_versions[:5]):
            published = version.get("published_at", "unknown date")
            if published and "T" in published:
                published = published.split("T")[0]
                
            click.echo(f"  {i+1}. {version['version']} (published: {published})")
        
        # Display compatibility scores
        compatibility_scores = dep_info.get("compatibility_scores", [])
        if compatibility_scores:
            click.echo("\n  Compatibility scores:")
            for score_info in compatibility_scores:
                version = score_info["version"]
                score = score_info["score"]
                
                # Color code based on score
                if score >= 0.8:
                    color = "green"
                elif score >= 0.6:
                    color = "yellow"
                else:
                    color = "red"
                    
                score_text = click.style(f"{score:.2f}", fg=color)
                click.echo(f"  {version}: {score_text}")
        
        # Display recommended update
        recommended = dep_info.get("recommended_update")
        if recommended:
            version = recommended["version"]
            score = recommended["compatibility_score"]
            
            click.echo(f"\n  Recommended update: {version} (compatibility: {score:.2f})")
        else:
            click.echo("\n  No recommended update available")


def display_update_plan(update_plan: Dict[str, Any]) -> None:
    """
    Display update plan in a user-friendly format.
    
    Args:
        update_plan: Update plan
    """
    click.echo("\nUpdate Plan:")
    click.echo("-" * 80)
    
    deps_to_update = update_plan.get("dependencies_to_update", [])
    
    if not deps_to_update:
        click.echo("No dependencies selected for update.")
        return
    
    click.echo(f"The following {len(deps_to_update)} dependencies will be updated:")
    
    for dep in deps_to_update:
        dep_name = dep["name"]
        current_version = dep["current_version"]
        target_version = dep["target_version"]
        score = dep.get("compatibility_score", 0)
        
        # Color code based on score
        if score >= 0.8:
            color = "green"
        elif score >= 0.6:
            color = "yellow"
        else:
            color = "red"
            
        score_text = click.style(f"{score:.2f}", fg=color)
        click.echo(f"\n{dep_name}: {current_version} → {target_version} (compatibility: {score_text})")
        
        # Display breaking changes if any
        breaking_changes = dep.get("breaking_changes", [])
        if breaking_changes:
            click.echo("  Breaking changes:")
            for change in breaking_changes:
                change_type = change.get("type", "unknown")
                symbol = change.get("symbol", "")
                description = change.get("description", "")
                
                click.echo(f"  - {change_type} in {symbol}: {description}")


if __name__ == "__main__":
    # This allows the command to be run directly for testing
    update(obj={})