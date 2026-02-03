from sqlalchemy import create_engine, Column, String, Integer, DateTime, Text, JSON, Float, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import uuid

from app.config import get_settings

settings = get_settings()

# Create engine
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Database Models
class Document(Base):
    """Document table for storing uploaded documents."""
    __tablename__ = "documents"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    filename = Column(String, nullable=False)
    content_type = Column(String)
    size_bytes = Column(Integer)
    upload_date = Column(DateTime, default=datetime.utcnow)
    chunk_count = Column(Integer, default=0)
    extra_data = Column(JSON, default={})
    
    # Relationships
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")


class DocumentChunk(Base):
    """Document chunks for search indexing."""
    __tablename__ = "document_chunks"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(String, ForeignKey("documents.id", ondelete="CASCADE"))
    chunk_index = Column(Integer)
    content = Column(Text, nullable=False)
    page_number = Column(Integer, nullable=True)
    extra_data = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    document = relationship("Document", back_populates="chunks")


class Conversation(Base):
    """Conversation table for managing chat sessions."""
    __tablename__ = "conversations"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    extra_data = Column(JSON, default={})
    
    # Relationships
    messages = relationship("ConversationMessage", back_populates="conversation", cascade="all, delete-orphan")
    search_history = relationship("SearchHistory", back_populates="conversation", cascade="all, delete-orphan")


class ConversationMessage(Base):
    """Messages within a conversation."""
    __tablename__ = "conversation_messages"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id = Column(String, ForeignKey("conversations.id", ondelete="CASCADE"))
    role = Column(String, nullable=False)  
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    extra_data = Column(JSON, default={})
    

    token_count = Column(Integer, default=0)
    
    # Relationships
    conversation = relationship("Conversation", back_populates="messages")


class SearchHistory(Base):
    """Search history for learning and optimization."""
    __tablename__ = "search_history"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id = Column(String, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=True)
    query = Column(Text, nullable=False)
    search_strategy = Column(String, nullable=False)  # keyword, semantic, hybrid
    results_count = Column(Integer, default=0)
    average_relevance = Column(Float, default=0.0)
    timestamp = Column(DateTime, default=datetime.utcnow)
    extra_data = Column(JSON, default={})
    
    # Relationships
    conversation = relationship("Conversation", back_populates="search_history")


class UserProfile(Base):
    """User interaction patterns for personalization."""
    __tablename__ = "user_profiles"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, unique=True, nullable=False)
    total_queries = Column(Integer, default=0)
    preferred_search_strategy = Column(String, nullable=True)
    avg_question_length = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    extra_data = Column(JSON, default={})


class AgentLog(Base):
    """Logging agent decisions for analysis."""
    __tablename__ = "agent_logs"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id = Column(String, nullable=True)
    agent_name = Column(String, nullable=False)
    decision = Column(String, nullable=False)
    reasoning = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)
    extra_data = Column(JSON, default={})


def init_db():
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine)
    print("Database initialized successfully!")


if __name__ == "__main__":
    init_db()
