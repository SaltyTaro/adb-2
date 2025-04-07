import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any

from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, 
    ForeignKey, JSON, Text, Enum, Table
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql.expression import text

from backend.core.db import Base


# Association tables
project_dependencies = Table(
    'project_dependencies',
    Base.metadata,
    Column('project_id', UUID(as_uuid=True), ForeignKey('projects.id')),
    Column('dependency_id', UUID(as_uuid=True), ForeignKey('dependencies.id')),
)

# Enums as strings for portability
ECOSYSTEM_TYPES = ['python', 'nodejs', 'other']
SEVERITY_LEVELS = ['critical', 'high', 'medium', 'low', 'info']
LICENSE_TYPES = ['permissive', 'copyleft', 'proprietary', 'unknown']
ANALYSIS_STATUS = ['pending', 'running', 'completed', 'failed']


class TimestampMixin:
    """Mixin for created/updated timestamps."""
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, 
        default=datetime.utcnow, 
        onupdate=datetime.utcnow, 
        nullable=False
    )


class User(Base, TimestampMixin):
    """User model for authentication and authorization."""
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    
    # Relationships
    projects = relationship("Project", back_populates="owner")
    api_keys = relationship("APIKey", back_populates="user")


class APIKey(Base, TimestampMixin):
    """API key for programmatic access."""
    __tablename__ = "api_keys"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key = Column(String, nullable=False, index=True)
    name = Column(String)
    expires_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    user = relationship("User", back_populates="api_keys")


class Project(Base, TimestampMixin):
    """Project model representing a codebase."""
    __tablename__ = "projects"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    description = Column(Text)
    repository_url = Column(String)
    ecosystem = Column(String, nullable=False)
    config = Column(JSONB, default={})
    
    # Relationships
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    owner = relationship("User", back_populates="projects")
    analyses = relationship("Analysis", back_populates="project")
    recommendations = relationship("Recommendation", back_populates="project")
    dependencies = relationship(
        "Dependency", 
        secondary=project_dependencies,
        back_populates="projects"
    )


class Dependency(Base, TimestampMixin):
    """Dependency model representing a library or package."""
    __tablename__ = "dependencies"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    ecosystem = Column(String, nullable=False)
    latest_version = Column(String)
    description = Column(Text)
    repository_url = Column(String)
    homepage_url = Column(String)
    
    # Dependency metadata
    metadata = Column(JSONB, default={})
    health_score = Column(Float)
    is_deprecated = Column(Boolean, default=False)
    
    # Relationships
    versions = relationship("DependencyVersion", back_populates="dependency")
    projects = relationship(
        "Project", 
        secondary=project_dependencies,
        back_populates="dependencies"
    )


class DependencyVersion(Base, TimestampMixin):
    """Specific version of a dependency."""
    __tablename__ = "dependency_versions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    version = Column(String, nullable=False)
    published_at = Column(DateTime)
    size_bytes = Column(Integer)
    is_yanked = Column(Boolean, default=False)
    
    # Detailed information
    licenses = Column(JSONB)  # List of licenses
    dependencies = Column(JSONB)  # Dict of dependencies
    
    # Analysis results
    security_vulnerabilities = Column(Integer, default=0)
    performance_score = Column(Float)
    
    # Relationships
    dependency_id = Column(UUID(as_uuid=True), ForeignKey("dependencies.id"))
    dependency = relationship("Dependency", back_populates="versions")
    vulnerability_reports = relationship("VulnerabilityReport", back_populates="version")
    license_reports = relationship("LicenseReport", back_populates="version")


class Analysis(Base, TimestampMixin):
    """Analysis model for a project's dependency analysis run."""
    __tablename__ = "analyses"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    status = Column(String, default="pending")
    analysis_type = Column(String, nullable=False)
    config = Column(JSONB, default={})
    result = Column(JSONB)
    error_message = Column(Text)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    
    # Relationships
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"))
    project = relationship("Project", back_populates="analyses")
    impact_scores = relationship("ImpactScore", back_populates="analysis")


class ImpactScore(Base, TimestampMixin):
    """Impact score for a dependency in a project."""
    __tablename__ = "impact_scores"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dependency_name = Column(String, nullable=False)
    version = Column(String, nullable=False)
    
    # Score components
    business_value_score = Column(Float)
    usage_score = Column(Float)
    complexity_score = Column(Float)
    health_score = Column(Float)
    overall_score = Column(Float, nullable=False)
    
    # Usage details
    used_features = Column(JSONB)  # Features actually used
    unused_features = Column(JSONB)  # Features included but unused
    
    # Relationships
    analysis_id = Column(UUID(as_uuid=True), ForeignKey("analyses.id"))
    analysis = relationship("Analysis", back_populates="impact_scores")


class VulnerabilityReport(Base, TimestampMixin):
    """Security vulnerability report for a dependency version."""
    __tablename__ = "vulnerability_reports"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cve_id = Column(String)
    title = Column(String, nullable=False)
    description = Column(Text)
    severity = Column(String, nullable=False)
    fixed_in = Column(String)  # Version where this is fixed
    exploitability_score = Column(Float)
    
    # Relationships
    version_id = Column(UUID(as_uuid=True), ForeignKey("dependency_versions.id"))
    version = relationship("DependencyVersion", back_populates="vulnerability_reports")


class LicenseReport(Base, TimestampMixin):
    """License compliance report for a dependency version."""
    __tablename__ = "license_reports"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    license_id = Column(String, nullable=False)
    license_name = Column(String)
    license_type = Column(String)
    license_text = Column(Text)
    risk_level = Column(String)
    
    # Compliance assessment
    is_compliant = Column(Boolean)
    compliance_notes = Column(Text)
    
    # Relationships
    version_id = Column(UUID(as_uuid=True), ForeignKey("dependency_versions.id"))
    version = relationship("DependencyVersion", back_populates="license_reports")


class Recommendation(Base, TimestampMixin):
    """Recommendation for dependency improvements."""
    __tablename__ = "recommendations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    recommendation_type = Column(String, nullable=False)
    severity = Column(String, nullable=False)
    impact = Column(Float)  # Estimated impact score
    effort = Column(Float)  # Estimated effort to implement
    code_changes = Column(JSONB)  # Suggested code changes
    
    # Metadata
    dependency_name = Column(String)
    from_version = Column(String)
    to_version = Column(String)
    
    # Relationships
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"))
    project = relationship("Project", back_populates="recommendations")