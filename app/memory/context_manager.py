"""Context engineering for intelligent context window management."""

from typing import List, Dict, Any, Optional
import tiktoken
from openai import OpenAI
import logging

from app.models import Message, MessageRole
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class ContextManager:
    """
    Manages context window with intelligent truncation and summarization.
    Ensures relevant information is preserved while respecting token limits.
    """
    
    def __init__(self):
        """Initialize context manager."""
        self.encoding = tiktoken.encoding_for_model("gpt-4")
        self.openai_client = OpenAI(api_key=settings.openai_api_key)
        self.max_tokens = settings.max_context_tokens
        self.compression_threshold = settings.context_compression_threshold
    
    def count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        return len(self.encoding.encode(text))
    
    def count_messages_tokens(self, messages: List[Message]) -> int:
        """Count total tokens in a list of messages."""
        total = 0
        for message in messages:
           
            total += self.count_tokens(message.role.value)
            total += self.count_tokens(message.content)
            total += 4  
        return total
    
    def optimize_context(
        self,
        messages: List[Message],
        additional_context: Optional[str] = None,
        preserve_recent: int = 3
    ) -> tuple[List[Message], str, int]:
        """
        Optimize context to fit within token limits.
        
        Strategy:
        1. Always preserve the most recent N messages
        2. Summarize older messages if needed
        3. Include additional context (search results) efficiently
        
        Args:
            messages: List of conversation messages
            additional_context: Additional context to include (e.g., search results)
            preserve_recent: Number of recent messages to always keep
            
        Returns:
            Tuple of (optimized_messages, context_summary, total_tokens)
        """
        if not messages:
            return [], additional_context or "", 0
        
        
        recent_messages = messages[-preserve_recent:] if len(messages) > preserve_recent else messages
        older_messages = messages[:-preserve_recent] if len(messages) > preserve_recent else []
        
        
        recent_tokens = self.count_messages_tokens(recent_messages)
        additional_tokens = self.count_tokens(additional_context) if additional_context else 0
        
        available_tokens = self.max_tokens - recent_tokens - additional_tokens
        
        logger.info(
            f"Context optimization: {len(messages)} messages, "
            f"recent={recent_tokens} tokens, additional={additional_tokens} tokens, "
            f"available={available_tokens} tokens"
        )
        
        
        if available_tokens > 0 and older_messages:
            older_tokens = self.count_messages_tokens(older_messages)
            
            if older_tokens <= available_tokens:
                
                optimized_messages = messages
                context_summary = ""
                total_tokens = recent_tokens + older_tokens + additional_tokens
            else:
                
                summary = self._summarize_messages(older_messages, max_tokens=available_tokens // 2)
                optimized_messages = recent_messages
                context_summary = f"Previous conversation summary: {summary}\n\n"
                total_tokens = recent_tokens + self.count_tokens(summary) + additional_tokens
        else:
            
            optimized_messages = recent_messages
            context_summary = ""
            total_tokens = recent_tokens + additional_tokens
        
        
        if total_tokens > self.max_tokens and additional_context:
            compressed_context = self._compress_context(
                additional_context,
                max_tokens=self.max_tokens - self.count_messages_tokens(optimized_messages)
            )
            additional_context = compressed_context
            total_tokens = self.count_messages_tokens(optimized_messages) + self.count_tokens(compressed_context)
        
        logger.info(f"Optimized context: {len(optimized_messages)} messages, {total_tokens} total tokens")
        
        return optimized_messages, context_summary + (additional_context or ""), total_tokens
    
    def _summarize_messages(
        self,
        messages: List[Message],
        max_tokens: int = 500
    ) -> str:
        """
        Summarize a list of messages using LLM.
        
        Args:
            messages: Messages to summarize
            max_tokens: Maximum tokens for summary
            
        Returns:
            Summary text
        """
        try:
            
            conversation_text = "\n".join([
                f"{msg.role.value.upper()}: {msg.content}"
                for msg in messages
            ])
            
            
            response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",  
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Summarize the following conversation concisely, "
                            "preserving key information, questions asked, and important context. "
                            f"Keep the summary under {max_tokens} tokens."
                        )
                    },
                    {
                        "role": "user",
                        "content": conversation_text
                    }
                ],
                max_tokens=max_tokens,
                temperature=0.3
            )
            
            summary = response.choices[0].message.content
            logger.info(f"Summarized {len(messages)} messages into {self.count_tokens(summary)} tokens")
            return summary
            
        except Exception as e:
            logger.error(f"Error summarizing messages: {e}")
            
            return f"Earlier conversation covered: {', '.join([msg.content[:50] for msg in messages[:3]])}..."
    
    def _compress_context(self, context: str, max_tokens: int) -> str:
        """
        Compress context text to fit within token limit.
        
        Args:
            context: Context text to compress
            max_tokens: Maximum tokens allowed
            
        Returns:
            Compressed context
        """
        current_tokens = self.count_tokens(context)
        
        if current_tokens <= max_tokens:
            return context
        

        ratio = max_tokens / current_tokens
        truncate_at = int(len(context) * ratio * 0.9)  
        
        compressed = context[:truncate_at] + "...\n[Context truncated due to length]"
        logger.info(f"Compressed context from {current_tokens} to {self.count_tokens(compressed)} tokens")
        
        return compressed
    
    def format_search_results_context(
        self,
        search_results: List[Dict[str, Any]],
        max_results: int = 5
    ) -> str:
        """
        Format search results into context string.
        
        Args:
            search_results: List of search result dictionaries
            max_results: Maximum number of results to include
            
        Returns:
            Formatted context string
        """
        if not search_results:
            return "No relevant documents found."
        
        context_parts = ["Relevant information from documents:\n"]
        
        for i, result in enumerate(search_results[:max_results], 1):
            doc_name = result.get('document_name', 'Unknown')
            content = result.get('content', '')
            page = result.get('page_number')
            score = result.get('relevance_score', 0)
            
            page_info = f" (Page {page})" if page else ""
            context_parts.append(
                f"\n[{i}] From '{doc_name}'{page_info} [Score: {score:.3f}]:\n{content}\n"
            )
        
        return "".join(context_parts)
    
    def should_compress(self, current_tokens: int) -> bool:
        """Check if context compression is needed."""
        return current_tokens >= self.compression_threshold
    
    def get_context_stats(
        self,
        messages: List[Message],
        additional_context: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get statistics about current context."""
        message_tokens = self.count_messages_tokens(messages)
        additional_tokens = self.count_tokens(additional_context) if additional_context else 0
        total_tokens = message_tokens + additional_tokens
        
        return {
            'message_count': len(messages),
            'message_tokens': message_tokens,
            'additional_context_tokens': additional_tokens,
            'total_tokens': total_tokens,
            'max_tokens': self.max_tokens,
            'utilization_percent': (total_tokens / self.max_tokens) * 100,
            'needs_compression': self.should_compress(total_tokens)
        }
