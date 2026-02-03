from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from datetime import datetime
import logging

from app.database import Conversation, ConversationMessage, SearchHistory, AgentLog
from app.models import Message, MessageRole, AgentDecision, SearchStrategy

logger = logging.getLogger(__name__)


class ConversationMemory:
    """
    Manages conversation persistence and retrieval.
    Provides multi-turn dialogue with context preservation.
    """
    
    def __init__(self, db: Session):
        """Initialize with database session."""
        self.db = db
    
    def create_conversation(
        self,
        title: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Create a new conversation."""
        conversation = Conversation(
            title=title or f"Conversation at {datetime.utcnow().isoformat()}",
            extra_data=metadata or {}
        )
        self.db.add(conversation)
        self.db.commit()
        self.db.refresh(conversation)
        
        logger.info(f"Created conversation {conversation.id}")
        return conversation.id
    
    def add_message(
        self,
        conversation_id: str,
        role: MessageRole,
        content: str,
        token_count: int = 0,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Add a message to a conversation."""
        message = ConversationMessage(
            conversation_id=conversation_id,
            role=role.value,
            content=content,
            token_count=token_count,
            extra_data=metadata or {}
        )
        self.db.add(message)
        
        
        conversation = self.db.query(Conversation).filter(
            Conversation.id == conversation_id
        ).first()
        if conversation:
            conversation.updated_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(message)
        
        logger.info(f"Added {role.value} message to conversation {conversation_id}")
        return message.id
    
    def get_conversation_messages(
        self,
        conversation_id: str,
        limit: Optional[int] = None
    ) -> List[Message]:
        """
        Get messages from a conversation.
        
        Args:
            conversation_id: Conversation ID
            limit: Maximum number of recent messages to return
            
        Returns:
            List of messages in chronological order
        """
        query = self.db.query(ConversationMessage).filter(
            ConversationMessage.conversation_id == conversation_id
        ).order_by(ConversationMessage.timestamp)
        
        if limit:
            
            query = query.limit(limit)
        
        messages = query.all()
        
        return [
            Message(
                role=MessageRole(msg.role),
                content=msg.content,
                timestamp=msg.timestamp,
                metadata=msg.extra_data or {}
            )
            for msg in messages
        ]
    
    def get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        """Get conversation by ID."""
        return self.db.query(Conversation).filter(
            Conversation.id == conversation_id
        ).first()
    
    def list_conversations(
        self,
        limit: int = 50,
        offset: int = 0
    ) -> List[Conversation]:
        """List all conversations."""
        return self.db.query(Conversation).order_by(
            Conversation.updated_at.desc()
        ).limit(limit).offset(offset).all()
    
    def delete_conversation(self, conversation_id: str) -> bool:
        """Delete a conversation and all its messages."""
        conversation = self.get_conversation(conversation_id)
        if conversation:
            self.db.delete(conversation)
            self.db.commit()
            logger.info(f"Deleted conversation {conversation_id}")
            return True
        return False
    
    def add_search_history(
        self,
        conversation_id: str,
        query: str,
        strategy: SearchStrategy,
        results_count: int,
        average_relevance: float,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Record search history for learning."""
        history = SearchHistory(
            conversation_id=conversation_id,
            query=query,
            search_strategy=strategy.value,
            results_count=results_count,
            average_relevance=average_relevance,
            extra_data=metadata or {}
        )
        self.db.add(history)
        self.db.commit()
        logger.info(f"Recorded search history for conversation {conversation_id}")
    
    def get_search_history(
        self,
        conversation_id: Optional[str] = None,
        limit: int = 10
    ) -> List[SearchHistory]:
        """Get search history, optionally filtered by conversation."""
        query = self.db.query(SearchHistory).order_by(
            SearchHistory.timestamp.desc()
        )
        
        if conversation_id:
            query = query.filter(SearchHistory.conversation_id == conversation_id)
        
        return query.limit(limit).all()
    
    def log_agent_decision(
        self,
        agent_decision: AgentDecision,
        conversation_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Log agent decisions for monitoring and analysis."""
        log = AgentLog(
            conversation_id=conversation_id,
            agent_name=agent_decision.agent_name,
            decision=agent_decision.decision,
            reasoning=agent_decision.reasoning,
            extra_data=metadata or {}
        )
        self.db.add(log)
        self.db.commit()
        logger.info(f"Logged decision from {agent_decision.agent_name}")
    
    def get_conversation_stats(self, conversation_id: str) -> Dict[str, Any]:
        """Get statistics about a conversation."""
        conversation = self.get_conversation(conversation_id)
        if not conversation:
            return {}
        
        message_count = self.db.query(ConversationMessage).filter(
            ConversationMessage.conversation_id == conversation_id
        ).count()
        
        total_tokens = self.db.query(ConversationMessage).filter(
            ConversationMessage.conversation_id == conversation_id
        ).with_entities(ConversationMessage.token_count).all()
        
        return {
            'conversation_id': conversation_id,
            'title': conversation.title,
            'created_at': conversation.created_at,
            'updated_at': conversation.updated_at,
            'message_count': message_count,
            'total_tokens': sum(t[0] for t in total_tokens if t[0]),
            'metadata': conversation.extra_data
        }
