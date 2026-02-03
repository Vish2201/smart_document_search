from typing import List, Dict, Any, Optional
import time
from app.models import SearchStrategy, Citation, AgentDecision

class Orchestrator:
    """
    Placeholder orchestrator to allow the application to run when the original
    agent logic is missing.
    """
    
    def process_query(
        self, 
        question: str, 
        conversation_context: List[Any] = None, 
        conversation_id: str = None
    ) -> Dict[str, Any]:
        """
        Process a query and return a dummy response.
        """
        start_time = time.time()
        
        # Simulate processing
        time.sleep(0.5)
        
        processing_time = (time.time() - start_time) * 1000
        
        return {
            'answer': "The agent system seems to be missing, but the application is running! This is a placeholder response.",
            'citations': [],
            'conversation_id': conversation_id,
            'search_strategy': SearchStrategy.HYBRID,
            'agent_decisions': [
                AgentDecision(
                    agent_name="System",
                    decision="Fallback",
                    reasoning="Agent system module was missing, using fallback."
                )
            ],
            'context_tokens_used': 0,
            'processing_time_ms': processing_time,
            'query_intent': "general"
        }

_orchestrator = None

def get_orchestrator() -> Orchestrator:
    """Get or create orchestrator instance."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = Orchestrator()
    return _orchestrator
