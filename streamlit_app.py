"""Streamlit UI for Smart Document Q&A System."""
import streamlit as st
import requests
import time
from datetime import datetime
from typing import List, Dict, Any

# Page config
st.set_page_config(
    page_title="Smart Document Q&A System",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin-bottom: 2rem;
    }
    .status-good {
        color: #10b981;
        font-weight: bold;
    }
    .status-bad {
        color: #ef4444;
        font-weight: bold;
    }
    .stat-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 10px;
        color: white;
        text-align: center;
    }
    .citation-box {
        background: #f0f4ff;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid #667eea;
        margin: 0.5rem 0;
    }
    .agent-decision {
        background: #fff7ed;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid #f59e0b;
        margin: 0.5rem 0;
    }
    .stButton>button {
        width: 100%;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        padding: 0.75rem;
        border-radius: 8px;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# API configuration
API_BASE = "http://localhost:8000"

# Initialize session state
if 'conversation_id' not in st.session_state:
    st.session_state.conversation_id = None
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'stats' not in st.session_state:
    st.session_state.stats = {
        'questions': 0,
        'total_tokens': 0,
        'response_times': []
    }

def check_health() -> Dict[str, Any]:
    """Check system health."""
    try:
        response = requests.get(f"{API_BASE}/health", timeout=5)
        return response.json()
    except Exception as e:
        return {
            "status": "error",
            "typesense_connected": False,
            "database_connected": False,
            "error": str(e)
        }

def get_documents() -> List[Dict]:
    """Get list of uploaded documents."""
    try:
        response = requests.get(f"{API_BASE}/api/v1/documents/", timeout=5)
        if response.ok:
            return response.json()
        return []
    except:
        return []

def upload_document(file) -> Dict[str, Any]:
    """Upload a document."""
    try:
        files = {'file': (file.name, file, file.type)}
        response = requests.post(f"{API_BASE}/api/v1/documents/upload", files=files, timeout=30)
        return response.json()
    except Exception as e:
        return {"error": str(e)}

def ask_question(question: str, use_context: bool = True) -> Dict[str, Any]:
    """Ask a question."""
    try:
        payload = {
            "question": question,
            "conversation_id": st.session_state.conversation_id,
            "use_context": use_context
        }
        response = requests.post(f"{API_BASE}/api/v1/ask", json=payload, timeout=60)
        data = response.json()
        
        if response.ok:
            st.session_state.conversation_id = data.get('conversation_id')
            
            # Update stats
            st.session_state.stats['questions'] += 1
            st.session_state.stats['total_tokens'] += data.get('context_tokens_used', 0)
            st.session_state.stats['response_times'].append(data.get('processing_time_ms', 0))
        
        return data
    except Exception as e:
        return {"error": str(e)}

# Header
st.markdown("""
<div class="main-header">
    <h1>🤖 Smart Document Q&A System</h1>
    <p>AI-powered document question answering with hybrid search and multi-agent orchestration</p>
</div>
""", unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.header("⚙️ System Status")
    
    # Check health
    health = check_health()
    
    if health.get('status') == 'error':
        st.markdown("### 🔴 API Server")
        st.error("Server is offline. Please start the server with:\n```python -m uvicorn app.main:app --port 8000```")
    else:
        st.markdown("### ✅ API Server")
        st.success("Connected")
        
        st.markdown("### Typesense Search")
        if health.get('typesense_connected'):
            st.markdown('<p class="status-good">✅ Connected</p>', unsafe_allow_html=True)
        else:
            st.markdown('<p class="status-bad">⚠️ Not running</p>', unsafe_allow_html=True)
            st.info("To enable full functionality, start Typesense:\n```docker run -d -p 8108:8108 typesense/typesense:26.0```")
        
        st.markdown("### Database")
        if health.get('database_connected'):
            st.markdown('<p class="status-good">✅ Connected</p>', unsafe_allow_html=True)
        else:
            st.markdown('<p class="status-bad">❌ Error</p>', unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Statistics
    st.header("📊 Statistics")
    
    documents = get_documents()
    st.metric("Documents", len(documents))
    st.metric("Questions Asked", st.session_state.stats['questions'])
    st.metric("Total Tokens Used", st.session_state.stats['total_tokens'])
    
    if st.session_state.stats['response_times']:
        avg_time = sum(st.session_state.stats['response_times']) / len(st.session_state.stats['response_times'])
        st.metric("Avg Response Time", f"{avg_time:.0f}ms")
    
    st.markdown("---")
    
    if st.button("🔄 Reset Conversation"):
        st.session_state.conversation_id = None
        st.session_state.messages = []
        st.success("Conversation reset!")
        st.rerun()

# Main content
tab1, tab2 = st.tabs(["💬 Chat", "📚 Documents"])

with tab1:
    st.header("Ask Questions About Your Documents")
    
    # Chat messages
    chat_container = st.container()
    
    with chat_container:
        if not st.session_state.messages:
            st.info("👋 Upload a document and start asking questions! The AI agents will analyze your query and provide well-sourced answers.")
        else:
            for msg in st.session_state.messages:
                if msg['role'] == 'user':
                    with st.chat_message("user", avatar="🧑"):
                        st.write(msg['content'])
                else:
                    with st.chat_message("assistant", avatar="🤖"):
                        st.write(msg['content'])
                        
                        # Show search strategy
                        if 'search_strategy' in msg:
                            strategy = msg['search_strategy']
                            if strategy == 'semantic':
                                st.markdown('`🔍 Semantic Search`')
                            elif strategy == 'keyword':
                                st.markdown('`🔑 Keyword Search`')
                            else:
                                st.markdown('`🔀 Hybrid Search`')
                        
                        # Show citations
                        if 'citations' in msg and msg['citations']:
                            with st.expander(f"📚 Sources ({len(msg['citations'])})"):
                                for i, citation in enumerate(msg['citations'], 1):
                                    st.markdown(f"""
                                    <div class="citation-box">
                                        <strong>{i}. {citation['document_name']}</strong> 
                                        <span style="color: #667eea;">(Relevance: {citation['relevance_score']*100:.0f}%)</span>
                                        <p style="font-size: 0.9rem; color: #666; margin-top: 0.5rem;">
                                            "{citation['chunk_text'][:200]}..."
                                        </p>
                                    </div>
                                    """, unsafe_allow_html=True)
                        
                        # Show agent decisions
                        if 'agent_decisions' in msg and msg['agent_decisions']:
                            with st.expander("🤖 Agent Reasoning"):
                                for decision in msg['agent_decisions']:
                                    st.markdown(f"""
                                    <div class="agent-decision">
                                        <strong>{decision['agent_name']}</strong>
                                        <p><strong>Decision:</strong> {decision['decision']}</p>
                                        <p style="font-size: 0.9rem; color: #666;">
                                            <strong>Reasoning:</strong> {decision['reasoning']}
                                        </p>
                                    </div>
                                    """, unsafe_allow_html=True)
                        
                        # Show metrics
                        if 'processing_time_ms' in msg:
                            col1, col2 = st.columns(2)
                            with col1:
                                st.caption(f"⏱️ {msg['processing_time_ms']:.0f}ms")
                            with col2:
                                st.caption(f"🎯 {msg.get('context_tokens_used', 0)} tokens")
    
    # Question input
    st.markdown("---")
    
    col1, col2 = st.columns([4, 1])
    
    with col1:
        question = st.text_input(
            "Your question",
            placeholder="What would you like to know about your documents?",
            label_visibility="collapsed",
            key="question_input"
        )
    
    with col2:
        use_context = st.checkbox("Use context", value=True, help="Include conversation history")
    
    if st.button("🚀 Ask Question", type="primary"):
        if not question:
            st.warning("Please enter a question!")
        else:
            # Add user message
            st.session_state.messages.append({
                'role': 'user',
                'content': question
            })
            
            # Show thinking
            with st.spinner("🤖 AI agents are analyzing your question..."):
                start_time = time.time()
                result = ask_question(question, use_context)
                
                if 'error' in result:
                    st.error(f"❌ Error: {result['error']}")
                else:
                    # Add assistant message
                    st.session_state.messages.append({
                        'role': 'assistant',
                        'content': result.get('answer', 'No answer generated'),
                        'search_strategy': result.get('search_strategy'),
                        'citations': result.get('citations', []),
                        'agent_decisions': result.get('agent_decisions', []),
                        'processing_time_ms': result.get('processing_time_ms', 0),
                        'context_tokens_used': result.get('context_tokens_used', 0)
                    })
                    
                    st.rerun()

with tab2:
    st.header("Document Management")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("📤 Upload Documents")
        
        uploaded_file = st.file_uploader(
            "Choose a file",
            type=['txt', 'md', 'markdown', 'text', 'pdf'],
            help="Upload .txt, .md, or .pdf files to add to the knowledge base"
        )
        
        if uploaded_file is not None:
            if st.button("Upload Document"):
                with st.spinner("Uploading and processing document..."):
                    result = upload_document(uploaded_file)
                    
                    if 'error' in result:
                        st.error(f"❌ Upload failed: {result['error']}")
                    elif 'detail' in result:
                        st.error(f"❌ {result['detail']}")
                    else:
                        st.success(f"✅ {result.get('message', 'Document uploaded successfully!')}")
                        st.info(f"Created {result.get('chunks_created', 0)} searchable chunks")
                        time.sleep(1)
                        st.rerun()
    
    with col2:
        st.subheader("📊 Quick Stats")
        
        docs = get_documents()
        total_chunks = sum(doc.get('chunk_count', 0) for doc in docs)
        
        st.markdown(f"""
        <div class="stat-card">
            <h2>{len(docs)}</h2>
            <p>Documents</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown(f"""
        <div class="stat-card" style="margin-top: 1rem;">
            <h2>{total_chunks}</h2>
            <p>Total Chunks</p>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    st.subheader("📋 Uploaded Documents")
    
    documents = get_documents()
    
    if not documents:
        st.info("No documents uploaded yet. Upload your first document above!")
    else:
        for doc in documents:
            with st.expander(f"📄 {doc['filename']}", expanded=False):
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("Chunks", doc['chunk_count'])
                
                with col2:
                    size_kb = doc['size_bytes'] / 1024
                    st.metric("Size", f"{size_kb:.1f} KB")
                
                with col3:
                    upload_date = datetime.fromisoformat(doc['upload_date'].replace('Z', '+00:00'))
                    st.metric("Uploaded", upload_date.strftime("%Y-%m-%d"))
                
                st.caption(f"Document ID: `{doc['document_id']}`")

# Footer
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #666; padding: 1rem;">
    <p><strong>Smart Document Q&A System</strong> • Powered by AI Agents with Hybrid Search</p>
    <p style="font-size: 0.9rem;">
        LangGraph Orchestration • Typesense Search • Context Engineering
    </p>
</div>
""", unsafe_allow_html=True)
