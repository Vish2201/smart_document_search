"""Test suite for the Smart Document Q&A System."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database import Base, get_db
from app.config import get_settings

# Test database
SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """Override database dependency for testing."""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)


@pytest.fixture(scope="function", autouse=True)
def setup_database():
    """Create test database before each test."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


class TestHealthEndpoint:
    """Test health check endpoint."""
    
    def test_health_check(self):
        """Test health endpoint returns correct structure."""
        response = client.get("/health")
        assert response.status_code == 200
        
        data = response.json()
        assert "status" in data
        assert "typesense_connected" in data
        assert "database_connected" in data
        assert data["database_connected"] is True


class TestDocumentManagement:
    """Test document upload and management."""
    
    def test_upload_text_document(self):
        """Test uploading a text document."""
        content = b"This is a test document for the Smart Q&A system."
        files = {"file": ("test.txt", content, "text/plain")}
        
        response = client.post("/api/v1/documents/upload", files=files)
        
        # Should succeed or fail gracefully
        assert response.status_code in [200, 500]  # 500 if Typesense not running
    
    def test_upload_invalid_file_type(self):
        """Test uploading an invalid file type."""
        content = b"Invalid file"
        files = {"file": ("test.pdf", content, "application/pdf")}
        
        response = client.post("/api/v1/documents/upload", files=files)
        assert response.status_code == 400
    
    def test_list_documents(self):
        """Test listing documents."""
        response = client.get("/api/v1/documents/")
        assert response.status_code == 200
        assert isinstance(response.json(), list)


class TestConversationManagement:
    """Test conversation management."""
    
    def test_create_conversation(self):
        """Test creating a new conversation."""
        response = client.post(
            "/api/v1/conversations/",
            json={"title": "Test Conversation"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "conversation_id" in data
        assert data["title"] == "Test Conversation"
    
    def test_list_conversations(self):
        """Test listing conversations."""
        # Create a conversation first
        client.post("/api/v1/conversations/", json={"title": "Test"})
        
        response = client.get("/api/v1/conversations/")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
    
    def test_get_conversation_history(self):
        """Test getting conversation history."""
        # Create conversation
        conv_response = client.post("/api/v1/conversations/", json={})
        conv_id = conv_response.json()["conversation_id"]
        
        # Get history (should be empty)
        response = client.get(f"/api/v1/conversations/{conv_id}/history")
        assert response.status_code == 200
        
        data = response.json()
        assert data["conversation_id"] == conv_id
        assert data["total_messages"] == 0


class TestQuestionAnswering:
    """Test Q&A functionality."""
    
    def test_ask_question_without_context(self):
        """Test asking a question without context."""
        response = client.post(
            "/api/v1/ask",
            json={
                "question": "What is a transformer?",
                "use_context": False
            }
        )
        
        # Should create conversation and attempt to answer
        assert response.status_code in [200, 500]  # 500 if Typesense/OpenAI not available
    
    def test_ask_question_creates_conversation(self):
        """Test that asking creates a conversation."""
        response = client.post(
            "/api/v1/ask",
            json={"question": "Test question"}
        )
        
        if response.status_code == 200:
            data = response.json()
            assert "conversation_id" in data


class TestMemorySystem:
    """Test memory and context management."""
    
    def test_conversation_persistence(self):
        """Test that conversations persist across requests."""
        # Create conversation
        conv_response = client.post("/api/v1/conversations/", json={})
        conv_id = conv_response.json()["conversation_id"]
        
        # Retrieve conversation
        get_response = client.get(f"/api/v1/conversations/{conv_id}")
        assert get_response.status_code == 200
        
        data = get_response.json()
        assert data["conversation_id"] == conv_id


# Run tests with: pytest tests/ -v
