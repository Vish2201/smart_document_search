import io
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

try:
    from pypdf import PdfReader
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    logger.warning("pypdf not available. PDF processing will be disabled.")


class DocumentProcessor:
    """Process documents into searchable chunks."""
    
    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50):
        """
        Initialize document processor.
        
        Args:
            chunk_size: Target size for each chunk (characters)
            chunk_overlap: Overlap between chunks (characters)
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
    
    def process_text_file(self, content: bytes, filename: str) -> List[Dict[str, Any]]:
        """
        Process a text file into chunks.
        
        Args:
            content: File content as bytes
            filename: Original filename
            
        Returns:
            List of chunk dictionaries
        """
        try:
            # Decode content
            text = content.decode('utf-8', errors='ignore')
            
            # Split into chunks
            chunks = self._chunk_text(text)
            
            # Format chunks
            formatted_chunks = []
            for i, chunk in enumerate(chunks):
                formatted_chunks.append({
                    'chunk_index': i,
                    'content': chunk,
                    'page_number': None,  # Text files don't have pages
                    'metadata': {'filename': filename}
                })
            
            logger.info(f"Processed text file '{filename}' into {len(chunks)} chunks")
            return formatted_chunks
            
        except Exception as e:
            logger.error(f"Error processing text file: {e}")
            return []
    
    def process_markdown_file(self, content: bytes, filename: str) -> List[Dict[str, Any]]:
        """Process markdown file into chunks."""
        # For now, treat like text file
        # Could add markdown-specific parsing later
        return self.process_text_file(content, filename)
    
    def process_pdf_file(self, content: bytes, filename: str) -> List[Dict[str, Any]]:
        """
        Process a PDF file into chunks.
        
        Args:
            content: PDF file content as bytes
            filename: Original filename
            
        Returns:
            List of chunk dictionaries with page numbers
        """
        if not PDF_AVAILABLE:
            raise ValueError("PDF processing not available. Install pypdf package.")
        
        try:
            # Create PDF reader from bytes
            pdf_file = io.BytesIO(content)
            reader = PdfReader(pdf_file)
            
            # Extract text from all pages
            full_text = ""
            page_texts = []
            
            for page_num, page in enumerate(reader.pages, start=1):
                try:
                    page_text = page.extract_text()
                    if page_text:
                        page_texts.append({
                            'page_number': page_num,
                            'text': page_text
                        })
                        full_text += f"\n\n[Page {page_num}]\n{page_text}"
                except Exception as e:
                    logger.warning(f"Error extracting text from page {page_num}: {e}")
                    continue
            
            if not full_text.strip():
                logger.error(f"No text extracted from PDF '{filename}'")
                return []
            
            # Split into chunks
            chunks = self._chunk_text(full_text.strip())
            
            # Format chunks with page numbers
            formatted_chunks = []
            for i, chunk in enumerate(chunks):
                # Try to determine which page this chunk is from
                page_num = self._estimate_page_number(chunk, page_texts)
                
                formatted_chunks.append({
                    'chunk_index': i,
                    'content': chunk,
                    'page_number': page_num,
                    'metadata': {
                        'filename': filename,
                        'total_pages': len(reader.pages)
                    }
                })
            
            logger.info(f"Processed PDF '{filename}' ({len(reader.pages)} pages) into {len(chunks)} chunks")
            return formatted_chunks
            
        except Exception as e:
            logger.error(f"Error processing PDF file: {e}")
            raise ValueError(f"Failed to process PDF: {str(e)}")
    
    def _estimate_page_number(self, chunk: str, page_texts: List[Dict]) -> Optional[int]:
        """Estimate which page a chunk comes from based on page markers."""
        # Look for page markers in the chunk
        for page_info in page_texts:
            page_marker = f"[Page {page_info['page_number']}]"
            if page_marker in chunk:
                return page_info['page_number']
        
        # If no marker found, return None
        return None
    
    def _chunk_text(self, text: str) -> List[str]:
        """
        Split text into overlapping chunks.
        
        Args:
            text: Full text content
            
        Returns:
            List of text chunks
        """
        # Clean text
        text = text.strip()
        
        if len(text) <= self.chunk_size:
            return [text]
        
        chunks = []
        start = 0
        
        while start < len(text):
            # Get chunk
            end = start + self.chunk_size
            
            # Try to break at sentence boundary
            if end < len(text):
                # Look for sentence end markers
                sentence_end = self._find_sentence_boundary(text, start, end)
                if sentence_end > start:
                    end = sentence_end
            
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            # Move start with overlap
            start = end - self.chunk_overlap
            
            # Prevent infinite loop
            if start <= chunks[-1] if chunks else False:
                start = end
        
        return chunks
    
    def _find_sentence_boundary(self, text: str, start: int, end: int) -> int:
        """Find a good sentence boundary near the end position."""
        # Look for sentence endings in the last 20% of the chunk
        search_start = end - (self.chunk_size // 5)
        search_text = text[search_start:end]
        
        # Find last sentence ending
        for delimiter in ['. ', '.\n', '! ', '!\n', '? ', '?\n']:
            pos = search_text.rfind(delimiter)
            if pos != -1:
                return search_start + pos + len(delimiter)
        
        # No sentence boundary found, return original end
        return end
    
    def estimate_chunks(self, content_length: int) -> int:
        """Estimate number of chunks for a given content length."""
        if content_length <= self.chunk_size:
            return 1
        
        effective_chunk_size = self.chunk_size - self.chunk_overlap
        return (content_length + effective_chunk_size - 1) // effective_chunk_size
