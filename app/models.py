
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class MessageRole(str, Enum):
    """Message role in conversation."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class SearchStrategy(str, Enum):
    """Search strategy types."""
    KEYWORD = "keyword"
    SEMANTIC = "semantic"
    HYBRID = "hybrid"


# Request Models
class QuestionRequest(BaseModel):
    """Request model for asking questions."""
    question: str = Field(..., min_length=1, max_length=1000)
    conversation_id: Optional[str] = None
    use_context: bool = True


class DocumentUploadResponse(BaseModel):
    """Response model for document upload."""
    document_id: str
    filename: str
    chunks_created: int
    message: str


class ConversationCreate(BaseModel):
    """Request model for creating a conversation."""
    title: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


# Response Models
class Citation(BaseModel):
    """Citation information for answers."""
    document_id: str
    document_name: str
    chunk_text: str
    relevance_score: float
    page_number: Optional[int] = None


class AgentDecision(BaseModel):
    """Agent decision tracking."""
    agent_name: str
    decision: str
    reasoning: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class Message(BaseModel):
    """Conversation message."""
    role: MessageRole
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Optional[Dict[str, Any]] = None


class AnswerResponse(BaseModel):
    """Response model for question answers."""
    answer: str
    citations: List[Citation]
    conversation_id: str
    search_strategy: SearchStrategy
    agent_decisions: List[AgentDecision]
    context_tokens_used: int
    processing_time_ms: float


class ConversationResponse(BaseModel):
    """Response model for conversation details."""
    conversation_id: str
    title: Optional[str]
    created_at: datetime
    updated_at: datetime
    message_count: int
    metadata: Optional[Dict[str, Any]] = None


class ConversationHistory(BaseModel):
    """Conversation history with all messages."""
    conversation_id: str
    messages: List[Message]
    total_messages: int


class DocumentInfo(BaseModel):
    """Document information."""
    document_id: str
    filename: str
    upload_date: datetime
    chunk_count: int
    size_bytes: int


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    typesense_connected: bool
    database_connected: bool
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# Internal Models for Agent State
class AgentState(BaseModel):
    """State shared across agents in LangGraph."""
    
    class Config:
        arbitrary_types_allowed = True
    
    # Input
    question: str
    conversation_id: Optional[str] = None
    
    # Query Analysis
    analyzed_query: Optional[str] = None
    search_strategy: Optional[SearchStrategy] = None
    query_intent: Optional[str] = None
    
    # Search Results
    search_results: List[Dict[str, Any]] = []
    
    # Context Management
    conversation_context: List[Message] = []
    relevant_context: Optional[str] = None
    context_tokens: int = 0
    
    # Final Answer
    answer: Optional[str] = None
    citations: List[Citation] = []
    
    # Agent Tracking
    agent_decisions: List[AgentDecision] = []
    
    # Metadata
    processing_start: datetime = Field(default_factory=datetime.utcnow)


class SearchQuery(BaseModel):
    """Search query with parameters."""
    query: str
    strategy: SearchStrategy = SearchStrategy.HYBRID
    max_results: int = 10
    keyword_weight: float = 0.5
    semantic_weight: float = 0.5
