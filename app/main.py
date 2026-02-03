from fastapi import FastAPI, UploadFile, File, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional
import logging
from datetime import datetime
import uuid

from app.config import get_settings
from app.database import get_db, init_db, Document, DocumentChunk
from app.models import (
    QuestionRequest, AnswerResponse, ConversationCreate, ConversationResponse,
    ConversationHistory, DocumentInfo, DocumentUploadResponse, HealthResponse,
    MessageRole,Message
)
from app.search.hybrid_search import get_search_engine
from app.memory.conversation import ConversationMemory
from app.memory.context_manager import ContextManager
from app.agents.orchestrator import get_orchestrator
from app.document_processor import DocumentProcessor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize app
settings = get_settings()
app = FastAPI(
    title="Smart Document Q&A System",
    description="AI-powered document Q&A with hybrid search and agent orchestration",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    """Initialize database and services."""
    logger.info("Starting Smart Document Q&A System...")
    init_db()
    logger.info("Database initialized")
    
    # Test connections
    try:
        search_engine = get_search_engine()
        health = search_engine.health_check()
        logger.info(f"Typesense connection: {'OK' if health else 'FAILED'}")
    except Exception as e:
        logger.warning(f"Typesense not available: {e}")


# Health check endpoint
@app.get("/health", response_model=HealthResponse)
async def health_check(db: Session = Depends(get_db)):
    """Check system health."""
    try:
        search_engine = get_search_engine()
        typesense_ok = search_engine.health_check()
    except:
        typesense_ok = False
    
    # Test database
    try:
        db.execute("SELECT 1")
        db_ok = True
    except:
        db_ok = False
    
    return HealthResponse(
        status="healthy" if (typesense_ok and db_ok) else "degraded",
        typesense_connected=typesense_ok,
        database_connected=db_ok
    )


# Document Management Endpoints
@app.post("/api/v1/documents/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Upload and process a document.
    
    Supported formats: .txt, .md, .pdf
    """
    try:
        # Validate file type
        allowed_extensions = ['.txt', '.md', '.text', '.markdown', '.pdf']
        file_ext = '.' + file.filename.split('.')[-1].lower()
        
        if file_ext not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type. Allowed: {', '.join(allowed_extensions)}"
            )
        
        # Read file content
        content = await file.read()
        
        # Create document record
        document = Document(
            filename=file.filename,
            content_type=file.content_type or 'text/plain',
            size_bytes=len(content),
            extra_data={'original_filename': file.filename}
        )
        db.add(document)
        db.flush()  # Get document ID
        
        # Process document into chunks
        processor = DocumentProcessor(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap
        )
        
        # Route to appropriate processor
        if file_ext == '.pdf':
            chunks = processor.process_pdf_file(content, file.filename)
        elif file_ext in ['.md', '.markdown']:
            chunks = processor.process_markdown_file(content, file.filename)
        else:
            chunks = processor.process_text_file(content, file.filename)
        
        if not chunks:
            raise HTTPException(status_code=400, detail="Failed to process document")
        
        # Store chunks in database and index in Typesense
        search_engine = get_search_engine()
        indexed_count = 0
        
        for chunk_data in chunks:
            # Create database record
            chunk = DocumentChunk(
                document_id=document.id,
                chunk_index=chunk_data['chunk_index'],
                content=chunk_data['content'],
                page_number=chunk_data.get('page_number'),
                extra_data=chunk_data.get('metadata', {})
            )
            db.add(chunk)
            db.flush()
            
            # Index in Typesense
            success = search_engine.index_document_chunk(
                chunk_id=chunk.id,
                document_id=document.id,
                document_name=file.filename,
                content=chunk_data['content'],
                chunk_index=chunk_data['chunk_index'],
                page_number=chunk_data.get('page_number')
            )
            
            if success:
                indexed_count += 1
        
        # Update document chunk count
        document.chunk_count = len(chunks)
        db.commit()
        
        logger.info(f"Uploaded document '{file.filename}': {indexed_count} chunks indexed")
        
        return DocumentUploadResponse(
            document_id=document.id,
            filename=file.filename,
            chunks_created=indexed_count,
            message=f"Document uploaded and processed into {indexed_count} chunks"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading document: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@app.get("/api/v1/documents/", response_model=List[DocumentInfo])
async def list_documents(
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """List all uploaded documents."""
    documents = db.query(Document).order_by(
        Document.upload_date.desc()
    ).limit(limit).offset(offset).all()
    
    return [
        DocumentInfo(
            document_id=doc.id,
            filename=doc.filename,
            upload_date=doc.upload_date,
            chunk_count=doc.chunk_count,
            size_bytes=doc.size_bytes
        )
        for doc in documents
    ]


@app.delete("/api/v1/documents/{document_id}")
async def delete_document(document_id: str, db: Session = Depends(get_db)):
    """Delete a document and all its chunks."""
    document = db.query(Document).filter(Document.id == document_id).first()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    try:
        # Delete from Typesense
        search_engine = get_search_engine()
        search_engine.delete_document_chunks(document_id)
        
        # Delete from database (cascades to chunks)
        db.delete(document)
        db.commit()
        
        logger.info(f"Deleted document {document_id}")
        return {"message": "Document deleted successfully", "document_id": document_id}
        
    except Exception as e:
        logger.error(f"Error deleting document: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")


# Conversation Management Endpoints
@app.post("/api/v1/conversations/", response_model=ConversationResponse)
async def create_conversation(
    request: ConversationCreate,
    db: Session = Depends(get_db)
):
    """Create a new conversation."""
    memory = ConversationMemory(db)
    conversation_id = memory.create_conversation(
        title=request.title,
        metadata=request.metadata
    )
    
    conversation = memory.get_conversation(conversation_id)
    
    return ConversationResponse(
        conversation_id=conversation.id,
        title=conversation.title,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        message_count=0,
        metadata=conversation.extra_data
    )


@app.get("/api/v1/conversations/", response_model=List[ConversationResponse])
async def list_conversations(
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """List all conversations."""
    memory = ConversationMemory(db)
    conversations = memory.list_conversations(limit=limit, offset=offset)
    
    return [
        ConversationResponse(
            conversation_id=conv.id,
            title=conv.title,
            created_at=conv.created_at,
            updated_at=conv.updated_at,
            message_count=len(conv.messages),
            metadata=conv.extra_data
        )
        for conv in conversations
    ]


@app.get("/api/v1/conversations/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(conversation_id: str, db: Session = Depends(get_db)):
    """Get conversation details."""
    memory = ConversationMemory(db)
    conversation = memory.get_conversation(conversation_id)
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    return ConversationResponse(
        conversation_id=conversation.id,
        title=conversation.title,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        message_count=len(conversation.messages),
        metadata=conversation.extra_data
    )


@app.get("/api/v1/conversations/{conversation_id}/history", response_model=ConversationHistory)
async def get_conversation_history(conversation_id: str, db: Session = Depends(get_db)):
    """Get full conversation history."""
    memory = ConversationMemory(db)
    messages = memory.get_conversation_messages(conversation_id)
    
    if not messages and not memory.get_conversation(conversation_id):
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    return ConversationHistory(
        conversation_id=conversation_id,
        messages=messages,
        total_messages=len(messages)
    )


# Q&A Endpoint
@app.post("/api/v1/ask", response_model=AnswerResponse)
async def ask_question(request: QuestionRequest, db: Session = Depends(get_db)):
    """
    Ask a question about the documents.
    
    This endpoint orchestrates the full agent workflow:
    1. Query analysis and strategy determination
    2. Hybrid search execution
    3. Context-aware response generation
    """
    try:
        memory = ConversationMemory(db)
        context_manager = ContextManager()
        
        # Get or create conversation
        if request.conversation_id:
            conversation = memory.get_conversation(request.conversation_id)
            if not conversation:
                raise HTTPException(status_code=404, detail="Conversation not found")
            conversation_id = request.conversation_id
        else:
            # Create new conversation
            conversation_id = memory.create_conversation(
                title=f"Q&A: {request.question[:50]}..."
            )
        
        # Add user message
        memory.add_message(
            conversation_id=conversation_id,
            role=MessageRole.USER,
            content=request.question,
            token_count=context_manager.count_tokens(request.question)
        )
        
        # Get conversation context if requested
        conversation_context = []
        if request.use_context:
            conversation_context = memory.get_conversation_messages(
                conversation_id,
                limit=settings.max_conversation_history
            )
        
        # Process query through agent orchestrator
        orchestrator = get_orchestrator()
        result = orchestrator.process_query(
            question=request.question,
            conversation_context=conversation_context,
            conversation_id=conversation_id
        )
        
        # Add assistant response to memory
        memory.add_message(
            conversation_id=conversation_id,
            role=MessageRole.ASSISTANT,
            content=result['answer'],
            token_count=context_manager.count_tokens(result['answer']),
            metadata={
                'citations_count': len(result['citations']),
                'search_strategy': result['search_strategy'].value if result['search_strategy'] else None,
                'query_intent': result.get('query_intent')
            }
        )
        
        # Log search history
        if result['citations']:
            avg_relevance = sum(c.relevance_score for c in result['citations']) / len(result['citations'])
            memory.add_search_history(
                conversation_id=conversation_id,
                query=request.question,
                strategy=result['search_strategy'],
                results_count=len(result['citations']),
                average_relevance=avg_relevance
            )
        
        # Log agent decisions
        for decision in result['agent_decisions']:
            memory.log_agent_decision(decision, conversation_id)
        
        return AnswerResponse(
            answer=result['answer'],
            citations=result['citations'],
            conversation_id=conversation_id,
            search_strategy=result['search_strategy'] or 'hybrid',
            agent_decisions=result['agent_decisions'],
            context_tokens_used=result['context_tokens_used'],
            processing_time_ms=result['processing_time_ms']
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing question: {e}")
        raise HTTPException(status_code=500, detail=f"Query processing failed: {str(e)}")


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Smart Document Q&A System",
        "version": "1.0.0",
        "description": "AI-powered document Q&A with hybrid search and multi-agent orchestration",
        "docs": "/docs",
        "health": "/health"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
