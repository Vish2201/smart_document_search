"""Hybrid search implementation using Typesense with keyword + vector search."""

import typesense
from typing import List, Dict, Any, Optional
from openai import OpenAI
import logging

from app.config import get_settings
from app.models import SearchStrategy, SearchQuery

logger = logging.getLogger(__name__)
settings = get_settings()


class HybridSearchEngine:
    """Hybrid search engine combining keyword and semantic search using Typesense."""
    
    COLLECTION_NAME = "document_chunks"
    
    def __init__(self):
        """Initialize Typesense client and OpenAI client."""
        self.client = typesense.Client({
            'nodes': [{
                'host': settings.typesense_host,
                'port': settings.typesense_port,
                'protocol': settings.typesense_protocol
            }],
            'api_key': settings.typesense_api_key,
            'connection_timeout_seconds': 10
        })
        
        self.openai_client = OpenAI(api_key=settings.openai_api_key)
        self._ensure_collection()
    
    def _ensure_collection(self):
        """Ensure the collection exists, create if not."""
        try:
            self.client.collections[self.COLLECTION_NAME].retrieve()
            logger.info(f"Collection '{self.COLLECTION_NAME}' exists")
        except typesense.exceptions.ObjectNotFound:
            logger.info(f"Creating collection '{self.COLLECTION_NAME}'")
            self._create_collection()
    
    def _create_collection(self):
        """Create Typesense collection with schema for hybrid search."""
        schema = {
            'name': self.COLLECTION_NAME,
            'fields': [
                {'name': 'id', 'type': 'string'},
                {'name': 'document_id', 'type': 'string', 'facet': True},
                {'name': 'document_name', 'type': 'string', 'facet': True},
                {'name': 'content', 'type': 'string'},
                {'name': 'chunk_index', 'type': 'int32'},
                {'name': 'page_number', 'type': 'int32', 'optional': True},
                {
                    'name': 'embedding',
                    'type': 'float[]',
                    'embed': {
                        'from': ['content'],
                        'model_config': {
                            'model_name': 'openai/text-embedding-3-small',
                            'api_key': settings.openai_api_key,
                            'dimensions': 1536
                        }
                    }
                }
            ],
            'default_sorting_field': 'chunk_index'
        }
        
        try:
            self.client.collections.create(schema)
            logger.info("Collection created successfully")
        except Exception as e:
            logger.error(f"Error creating collection: {e}")
            raise
    
    def index_document_chunk(
        self,
        chunk_id: str,
        document_id: str,
        document_name: str,
        content: str,
        chunk_index: int,
        page_number: Optional[int] = None
    ) -> bool:
        """Index a document chunk with its embedding."""
        try:
            # Generate embedding using OpenAI
            embedding_response = self.openai_client.embeddings.create(
                model=settings.embedding_model,
                input=content
            )
            embedding = embedding_response.data[0].embedding
            
            # Prepare document for indexing
            document = {
                'id': chunk_id,
                'document_id': document_id,
                'document_name': document_name,
                'content': content,
                'chunk_index': chunk_index,
                'embedding': embedding
            }
            
            if page_number is not None:
                document['page_number'] = page_number
            
            # Index in Typesense
            self.client.collections[self.COLLECTION_NAME].documents.upsert(document)
            logger.info(f"Indexed chunk {chunk_id} from document {document_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error indexing chunk {chunk_id}: {e}")
            return False
    
    def hybrid_search(
        self,
        query: str,
        strategy: SearchStrategy = SearchStrategy.HYBRID,
        max_results: int = 10,
        keyword_weight: float = 0.5,
        semantic_weight: float = 0.5,
        document_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Perform hybrid search combining keyword and semantic search.
        
        Args:
            query: Search query
            strategy: Search strategy (keyword, semantic, or hybrid)
            max_results: Maximum number of results
            keyword_weight: Weight for keyword search (0-1)
            semantic_weight: Weight for semantic search (0-1)
            document_filter: Optional document ID filter
            
        Returns:
            List of search results with relevance scores
        """
        try:
            # Generate query embedding for semantic search
            embedding_response = self.openai_client.embeddings.create(
                model=settings.embedding_model,
                input=query
            )
            query_embedding = embedding_response.data[0].embedding
            
            # Build search parameters based on strategy
            search_params = {
                'q': query,
                'query_by': 'content',
                'per_page': max_results,
                'include_fields': 'id,document_id,document_name,content,chunk_index,page_number'
            }
            
            # Add document filter if specified
            if document_filter:
                search_params['filter_by'] = f'document_id:={document_filter}'
            
            # Configure search strategy
            if strategy == SearchStrategy.KEYWORD:
                # Pure keyword search
                search_params['query_by_weights'] = '1'
                
            elif strategy == SearchStrategy.SEMANTIC:
                # Pure semantic/vector search
                search_params['vector_query'] = f'embedding:([{",".join(map(str, query_embedding))}], k:{max_results})'
                search_params['q'] = '*'  # Wildcard for vector-only search
                
            elif strategy == SearchStrategy.HYBRID:
                # Hybrid search combining both
                search_params['vector_query'] = f'embedding:([{",".join(map(str, query_embedding))}], k:{max_results}, alpha:{semantic_weight})'
                # Alpha parameter balances keyword vs semantic
            
            # Execute search
            results = self.client.collections[self.COLLECTION_NAME].documents.search(search_params)
            
            # Process and format results
            formatted_results = []
            for hit in results.get('hits', []):
                doc = hit['document']
                formatted_results.append({
                    'chunk_id': doc['id'],
                    'document_id': doc['document_id'],
                    'document_name': doc['document_name'],
                    'content': doc['content'],
                    'chunk_index': doc.get('chunk_index', 0),
                    'page_number': doc.get('page_number'),
                    'relevance_score': hit.get('vector_distance', hit.get('text_match', 0)),
                    'text_match_score': hit.get('text_match', 0)
                })
            
            logger.info(f"Search returned {len(formatted_results)} results using {strategy.value} strategy")
            return formatted_results
            
        except Exception as e:
            logger.error(f"Error during hybrid search: {e}")
            return []
    
    def delete_document_chunks(self, document_id: str) -> bool:
        """Delete all chunks for a document."""
        try:
            self.client.collections[self.COLLECTION_NAME].documents.delete({
                'filter_by': f'document_id:={document_id}'
            })
            logger.info(f"Deleted all chunks for document {document_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting document chunks: {e}")
            return False
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """Get statistics about the collection."""
        try:
            collection = self.client.collections[self.COLLECTION_NAME].retrieve()
            return {
                'name': collection['name'],
                'num_documents': collection['num_documents'],
                'created_at': collection.get('created_at')
            }
        except Exception as e:
            logger.error(f"Error getting collection stats: {e}")
            return {}
    
    def health_check(self) -> bool:
        """Check if Typesense is healthy."""
        try:
            health = self.client.health.retrieve()
            return health.get('ok', False)
        except Exception as e:
            logger.error(f"Typesense health check failed: {e}")
            return False


# Singleton instance
_search_engine: Optional[HybridSearchEngine] = None


def get_search_engine() -> HybridSearchEngine:
    """Get or create search engine singleton."""
    global _search_engine
    if _search_engine is None:
        _search_engine = HybridSearchEngine()
    return _search_engine
