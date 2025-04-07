import os
import sys
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.core.db import Base
from backend.core.config import get_settings
from backend.core.models import User, Project, Dependency
from backend.api.auth import get_password_hash
from backend.main import app

# Override settings for testing
os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["SECRET_KEY"] = "test_secret_key"
os.environ["ENABLE_AI_FEATURES"] = "false"


@pytest.fixture(scope="session")
def test_settings():
    """Get test settings"""
    return get_settings()


@pytest.fixture(scope="session")
def test_engine():
    """Create a test database engine"""
    settings = get_settings()
    engine = create_engine(settings.DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    return engine


@pytest.fixture(scope="function")
def db_session(test_engine):
    """Create a new database session for a test"""
    # Create a new session for each test
    Session = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    session = Session()
    
    try:
        yield session
    finally:
        session.close()
        
    # Clear tables after each test
    for table in reversed(Base.metadata.sorted_tables):
        test_engine.execute(table.delete())


@pytest.fixture
def client(db_session):
    """Create a test client for the FastAPI app"""
    # Override the get_db dependency to use the test database
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    
    app.dependency_overrides = {}
    app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def test_user(db_session):
    """Create a test user"""
    user = User(
        username="testuser",
        email="test@example.com",
        hashed_password=get_password_hash("password123"),
        is_active=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_project(db_session, test_user):
    """Create a test project"""
    project = Project(
        name="Test Project",
        description="A project for testing",
        ecosystem="python",
        owner_id=test_user.id
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    return project


@pytest.fixture
def test_dependency(db_session):
    """Create a test dependency"""
    dependency = Dependency(
        name="requests",
        ecosystem="python",
        latest_version="2.28.1",
        description="Python HTTP library",
        repository_url="https://github.com/psf/requests",
        health_score=0.85
    )
    db_session.add(dependency)
    db_session.commit()
    db_session.refresh(dependency)
    return dependency


@pytest.fixture
def auth_token(client, test_user):
    """Get an authentication token for the test user"""
    response = client.post(
        "/api/v1/auth/token",
        data={
            "username": "testuser",
            "password": "password123"
        }
    )
    return response.json()["access_token"]


@pytest.fixture
def auth_headers(auth_token):
    """Get headers with authorization token"""
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture
def test_data_dir():
    """Get path to test data directory"""
    return os.path.join(os.path.dirname(__file__), "data")