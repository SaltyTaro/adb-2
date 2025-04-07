import os
import sys
import click
import json
import requests
import logging
import tabulate
from typing import Dict, List, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


@click.command()
@click.option("--project-id", "-p", required=True, help="Project ID")
@click.option("--analysis-id", "-a", help="Analysis ID (if only showing one analysis)")
@click.option("--format", "-f", default="text", type=click.Choice(["text", "json", "markdown", "html"]), 
              help="Output format")
@click.option("--output", "-o", help="Output file for results")
@click.option("--include-details/--no-details", default=False, help="Include detailed results")
@click.pass_context
def report(ctx, project_id, analysis_id, format, output, include_details):
    """
    Generate a report based on analysis results.
    
    This command formats and presents analysis results in various output formats.
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
        
        # Get analyses or specific analysis
        analyses = []
        if analysis_id:
            analysis = get_analysis(api_url, headers, analysis_id)
            analyses = [analysis]
        else:
            # Get all analyses for the project
            analyses = get_project_analyses(api_url, headers, project_id)
        
        # Generate report
        if format == "json":
            report_data = generate_json_report(project, analyses, include_details)
            if output:
                with open(output, "w") as f:
                    json.dump(report_data, f, indent=2)
                logger.info(f"JSON report saved to {output}")
            else:
                click.echo(json.dumps(report_data, indent=2))
        
        elif format == "markdown":
            report_text = generate_markdown_report(project, analyses, include_details)
            if output:
                with open(output, "w") as f:
                    f.write(report_text)
                logger.info(f"Markdown report saved to {output}")
            else:
                click.echo(report_text)
        
        elif format == "html":
            report_html = generate_html_report(project, analyses, include_details)
            if output:
                with open(output, "w") as f:
                    f.write(report_html)
                logger.info(f"HTML report saved to {output}")
            else:
                click.echo(report_html)
        
        else:  # Default to text format
            report_text = generate_text_report(project, analyses, include_details)
            if output:
                with open(output, "w") as f:
                    f.write(report_text)
                logger.info(f"Text report saved to {output}")
            else:
                click.echo(report_text)
        
        return True
    
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
        logger.error(f"Error generating report: {str(e)}")
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


def get_analysis(api_url: str, headers: Dict[str, str], analysis_id: str) -> Dict[str, Any]:
    """
    Get analysis information from the API.
    
    Args:
        api_url: API URL
        headers: Request headers
        analysis_id: Analysis ID
        
    Returns:
        Analysis data
    """
    response = requests.get(
        f"{api_url}/analyses/{analysis_id}",
        headers=headers
    )
    response.raise_for_status()
    
    return response.json()


def get_project_analyses(api_url: str, headers: Dict[str, str], project_id: str) -> List[Dict[str, Any]]:
    """
    Get all analyses for a project.
    
    Args:
        api_url: API URL
        headers: Request headers
        project_id: Project ID
        
    Returns:
        List of analysis data
    """
    response = requests.get(
        f"{api_url}/projects/{project_id}/analyses",
        headers=headers
    )
    response.raise_for_status()
    
    return response.json()


def generate_json_report(project: Dict[str, Any], analyses: List[Dict[str, Any]], include_details: bool) -> Dict[str, Any]:
    """
    Generate a JSON report.
    
    Args:
        project: Project data
        analyses: Analysis data
        include_details: Whether to include detailed results
        
    Returns:
        JSON report data
    """
    report = {
        "project": {
            "id": project.get("id"),
            "name": project.get("name"),
            "ecosystem": project.get("ecosystem"),
            "description": project.get("description")
        },
        "report_generated": datetime.utcnow().isoformat(),
        "analyses": []
    }
    
    for analysis in analyses:
        analysis_data = {
            "id": analysis.get("id"),
            "type": analysis.get("analysis_type"),
            "status": analysis.get("status"),
            "created_at": analysis.get("created_at"),
            "completed_at": analysis.get("completed_at"),
            "summary": analysis.get("result", {})
        }
        
        if include_details and analysis.get("detailed_results"):
            analysis_data["details"] = analysis.get("detailed_results")
        
        report["analyses"].append(analysis_data)
    
    return report


def generate_text_report(project: Dict[str, Any], analyses: List[Dict[str, Any]], include_details: bool) -> str:
    """
    Generate a plain text report.
    
    Args:
        project: Project data
        analyses: Analysis data
        include_details: Whether to include detailed results
        
    Returns:
        Text report
    """
    report_lines = []
    
    # Project information
    report_lines.append("=" * 80)
    report_lines.append(f"DEPENDENCY INTELLIGENCE REPORT")
    report_lines.append("=" * 80)
    report_lines.append(f"Project: {project.get('name')} (ID: {project.get('id')})")
    report_lines.append(f"Ecosystem: {project.get('ecosystem')}")
    if project.get("description"):
        report_lines.append(f"Description: {project.get('description')}")
    report_lines.append(f"Report Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    report_lines.append("-" * 80)
    
    # Analysis summaries
    report_lines.append(f"\nANALYSES SUMMARY ({len(analyses)} total)")
    report_lines.append("-" * 80)
    
    if not analyses:
        report_lines.append("No analyses found for this project.")
    else:
        # Create a table of analyses
        table_data = []
        for analysis in analyses:
            created_at = analysis.get("created_at", "")
            if created_at:
                created_at = created_at.split("T")[0]
                
            completed_at = analysis.get("completed_at", "")
            if completed_at:
                completed_at = completed_at.split("T")[0]
                
            table_data.append([
                analysis.get("id", "")[:8] + "...",
                analysis.get("analysis_type", ""),
                analysis.get("status", ""),
                created_at,
                completed_at
            ])
        
        headers = ["ID", "Type", "Status", "Created", "Completed"]
        report_lines.append(tabulate.tabulate(table_data, headers=headers, tablefmt="grid"))
    
    # Detailed analysis results
    if include_details:
        for analysis in analyses:
            report_lines.append("\n" + "=" * 80)
            report_lines.append(f"ANALYSIS: {analysis.get('analysis_type', '').upper()}")
            report_lines.append("-" * 80)
            report_lines.append(f"ID: {analysis.get('id')}")
            report_lines.append(f"Status: {analysis.get('status')}")
            report_lines.append(f"Created: {analysis.get('created_at')}")
            report_lines.append(f"Completed: {analysis.get('completed_at')}")
            
            # Results summary
            if analysis.get("result"):
                report_lines.append("\nRESULT SUMMARY:")
                result = analysis.get("result", {})
                for key, value in result.items():
                    if isinstance(value, dict):
                        report_lines.append(f"  {key}:")
                        for subkey, subvalue in value.items():
                            report_lines.append(f"    {subkey}: {subvalue}")
                    else:
                        report_lines.append(f"  {key}: {value}")
            
            # Detailed results
            if analysis.get("detailed_results"):
                report_lines.append("\nDETAILED RESULTS:")
                report_lines.append(json.dumps(analysis.get("detailed_results"), indent=2))
    
    return "\n".join(report_lines)


def generate_markdown_report(project: Dict[str, Any], analyses: List[Dict[str, Any]], include_details: bool) -> str:
    """
    Generate a Markdown report.
    
    Args:
        project: Project data
        analyses: Analysis data
        include_details: Whether to include detailed results
        
    Returns:
        Markdown report
    """
    report_lines = []
    
    # Project information
    report_lines.append("# Dependency Intelligence Report")
    report_lines.append(f"## Project: {project.get('name')}")
    report_lines.append(f"**ID:** {project.get('id')}  ")
    report_lines.append(f"**Ecosystem:** {project.get('ecosystem')}  ")
    if project.get("description"):
        report_lines.append(f"**Description:** {project.get('description')}  ")
    report_lines.append(f"**Report Generated:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}  ")
    report_lines.append("")
    
    # Analysis summaries
    report_lines.append(f"## Analyses Summary ({len(analyses)} total)")
    
    if not analyses:
        report_lines.append("No analyses found for this project.")
    else:
        # Create a table of analyses
        report_lines.append("| ID | Type | Status | Created | Completed |")
        report_lines.append("|---|---|---|---|---|")
        
        for analysis in analyses:
            created_at = analysis.get("created_at", "")
            if created_at:
                created_at = created_at.split("T")[0]
                
            completed_at = analysis.get("completed_at", "")
            if completed_at:
                completed_at = completed_at.split("T")[0]
                
            report_lines.append(
                f"| {analysis.get('id', '')[:8]}... | "
                f"{analysis.get('analysis_type', '')} | "
                f"{analysis.get('status', '')} | "
                f"{created_at} | "
                f"{completed_at} |"
            )
    
    # Detailed analysis results
    if include_details:
        for analysis in analyses:
            report_lines.append("")
            report_lines.append(f"## Analysis: {analysis.get('analysis_type', '').upper()}")
            report_lines.append(f"**ID:** {analysis.get('id')}  ")
            report_lines.append(f"**Status:** {analysis.get('status')}  ")
            report_lines.append(f"**Created:** {analysis.get('created_at')}  ")
            report_lines.append(f"**Completed:** {analysis.get('completed_at')}  ")
            
            # Results summary
            if analysis.get("result"):
                report_lines.append("\n### Result Summary")
                result = analysis.get("result", {})
                report_lines.append("```json")
                report_lines.append(json.dumps(result, indent=2))
                report_lines.append("```")
            
            # Detailed results
            if analysis.get("detailed_results"):
                report_lines.append("\n### Detailed Results")
                report_lines.append("```json")
                report_lines.append(json.dumps(analysis.get("detailed_results"), indent=2))
                report_lines.append("```")
    
    return "\n".join(report_lines)


def generate_html_report(project: Dict[str, Any], analyses: List[Dict[str, Any]], include_details: bool) -> str:
    """
    Generate an HTML report.
    
    Args:
        project: Project data
        analyses: Analysis data
        include_details: Whether to include detailed results
        
    Returns:
        HTML report
    """
    html_lines = []
    
    # HTML header
    html_lines.append("<!DOCTYPE html>")
    html_lines.append("<html lang=\"en\">")
    html_lines.append("<head>")
    html_lines.append("  <meta charset=\"UTF-8\">")
    html_lines.append("  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">")
    html_lines.append("  <title>Dependency Intelligence Report</title>")
    html_lines.append("  <style>")
    html_lines.append("    body { font-family: Arial, sans-serif; line-height: 1.6; margin: 0; padding: 20px; color: #333; }")
    html_lines.append("    h1, h2, h3 { color: #2c3e50; }")
    html_lines.append("    h1 { border-bottom: 2px solid #3498db; padding-bottom: 10px; }")
    html_lines.append("    h2 { border-bottom: 1px solid #bdc3c7; padding-bottom: 5px; margin-top: 30px; }")
    html_lines.append("    h3 { margin-top: 25px; }")
    html_lines.append("    .container { max-width: 1200px; margin: 0 auto; }")
    html_lines.append("    .project-info { background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin-bottom: 20px; }")
    html_lines.append("    .analysis { margin-bottom: 30px; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }")
    html_lines.append("    .analysis-header { display: flex; justify-content: space-between; margin-bottom: 10px; }")
    html_lines.append("    .status { font-weight: bold; }")
    html_lines.append("    .status-completed { color: green; }")
    html_lines.append("    .status-failed { color: red; }")
    html_lines.append("    .status-running { color: orange; }")
    html_lines.append("    table { width: 100%; border-collapse: collapse; margin: 20px 0; }")
    html_lines.append("    th, td { padding: 12px 15px; text-align: left; border-bottom: 1px solid #ddd; }")
    html_lines.append("    th { background-color: #f2f2f2; }")
    html_lines.append("    tr:hover { background-color: #f5f5f5; }")
    html_lines.append("    pre { background-color: #f8f9fa; padding: 15px; border-radius: 5px; overflow-x: auto; }")
    html_lines.append("    code { font-family: Monaco, Consolas, monospace; }")
    html_lines.append("  </style>")
    html_lines.append("</head>")
    html_lines.append("<body>")
    html_lines.append("  <div class=\"container\">")
    
    # Project information
    html_lines.append("    <h1>Dependency Intelligence Report</h1>")
    html_lines.append("    <div class=\"project-info\">")
    html_lines.append(f"      <h2>{project.get('name', 'Project')}</h2>")
    html_lines.append(f"      <p><strong>ID:</strong> {project.get('id')}</p>")
    html_lines.append(f"      <p><strong>Ecosystem:</strong> {project.get('ecosystem')}</p>")
    if project.get("description"):
        html_lines.append(f"      <p><strong>Description:</strong> {project.get('description')}</p>")
    html_lines.append(f"      <p><strong>Report Generated:</strong> {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}</p>")
    html_lines.append("    </div>")
    
    # Analysis summaries
    html_lines.append(f"    <h2>Analyses Summary ({len(analyses)} total)</h2>")
    
    if not analyses:
        html_lines.append("    <p>No analyses found for this project.</p>")
    else:
        # Create a table of analyses
        html_lines.append("    <table>")
        html_lines.append("      <thead>")
        html_lines.append("        <tr>")
        html_lines.append("          <th>ID</th>")
        html_lines.append("          <th>Type</th>")
        html_lines.append("          <th>Status</th>")
        html_lines.append("          <th>Created</th>")
        html_lines.append("          <th>Completed</th>")
        html_lines.append("        </tr>")
        html_lines.append("      </thead>")
        html_lines.append("      <tbody>")
        
        for analysis in analyses:
            created_at = analysis.get("created_at", "")
            if created_at:
                created_at = created_at.split("T")[0]
                
            completed_at = analysis.get("completed_at", "")
            if completed_at:
                completed_at = completed_at.split("T")[0]
                
            status = analysis.get("status", "")
            status_class = f"status-{status.lower()}" if status else ""
            
            html_lines.append("        <tr>")
            html_lines.append(f"          <td>{analysis.get('id', '')[:8]}...</td>")
            html_lines.append(f"          <td>{analysis.get('analysis_type', '')}</td>")
            html_lines.append(f"          <td class=\"status {status_class}\">{status}</td>")
            html_lines.append(f"          <td>{created_at}</td>")
            html_lines.append(f"          <td>{completed_at}</td>")
            html_lines.append("        </tr>")
        
        html_lines.append("      </tbody>")
        html_lines.append("    </table>")
    
    # Detailed analysis results
    if include_details:
        for analysis in analyses:
            html_lines.append(f"    <div class=\"analysis\">")
            html_lines.append(f"      <h2>Analysis: {analysis.get('analysis_type', '').upper()}</h2>")
            html_lines.append("      <div class=\"analysis-header\">")
            html_lines.append(f"        <p><strong>ID:</strong> {analysis.get('id')}</p>")
            
            status = analysis.get("status", "")
            status_class = f"status-{status.lower()}" if status else ""
            html_lines.append(f"        <p><strong>Status:</strong> <span class=\"status {status_class}\">{status}</span></p>")
            
            html_lines.append("      </div>")
            html_lines.append(f"      <p><strong>Created:</strong> {analysis.get('created_at')}</p>")
            html_lines.append(f"      <p><strong>Completed:</strong> {analysis.get('completed_at')}</p>")
            
            # Results summary
            if analysis.get("result"):
                html_lines.append("      <h3>Result Summary</h3>")
                html_lines.append("      <pre><code>")
                html_lines.append(json.dumps(analysis.get("result"), indent=2))
                html_lines.append("      </code></pre>")
            
            # Detailed results
            if analysis.get("detailed_results"):
                html_lines.append("      <h3>Detailed Results</h3>")
                html_lines.append("      <pre><code>")
                html_lines.append(json.dumps(analysis.get("detailed_results"), indent=2))
                html_lines.append("      </code></pre>")
            
            html_lines.append("    </div>")
    
    # HTML footer
    html_lines.append("  </div>")
    html_lines.append("</body>")
    html_lines.append("</html>")
    
    return "\n".join(html_lines)


if __name__ == "__main__":
    # This allows the command to be run directly for testing
    report(obj={})