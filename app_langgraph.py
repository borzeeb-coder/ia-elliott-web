"""
ELLIOTT - Agent IA Avance avec LangGraph
Memoire longue terme (RAG) + Recherche Web
"""
import os
from typing import TypedDict, Annotated, Sequence
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.tools import tool
from langchain_tavily import TavilySearchResults
from langchain_community.vectorstores import Chroma
from langchain_community.document_loaders import TextLoader
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from flask import Flask, request, Response
import json as _json

# =============================================================================
# CONFIGURATION
# =============================================================================
os.environ["OPENAI_API_KEY"] = os.environ.get("OPENAI_API_KEY", "your-openai-api-key")
os.environ["TAVILY_API_KEY"] = os.environ.get("TAVILY_API_KEY", "your-tavily-api-key")

# =============================================================================
# STATE
# =============================================================================
class AgentState(TypedDict):
    messages: Annotated[Sequence[HumanMessage | AIMessage], add_messages]
    context: str

# =============================================================================
# TOOLS
# =============================================================================
tavily = TavilySearchResults(max_results=3)

@tool
def web_search(query: str) -> str:
    """Recherche des informations recentes sur le web."""
    results = tavily.invoke(query)
    return "\n".join([r["content"] for r in results])

tools = [web_search]

# =============================================================================
# VECTOR STORE (RAG)
# =============================================================================
embeddings = OpenAIEmbeddings()
vectorstore = Chroma.from_texts(
    ["ELLIOTT est un assistant IA intelligent et polyvalent.",
     "ELLIOTT peut coder, expliquer, creer, ecrire, traduire.",
     "ELLIOTT utilise LangGraph pour la gestion d'etats.",
     "ELLIOTT a une memoire longue terme avec RAG."],
    embedding=embeddings,
    persist_directory="./chroma_db"
)
retriever = vectorstore.as_retriever(search_kwargs={"k": 2})

# =============================================================================
# LLM
# =============================================================================
llm = ChatOpenAI(model="gpt-4o", temperature=0)
llm_with_tools = llm.bind_tools(tools)

# =============================================================================
# NODES
# =============================================================================
def agent_node(state: AgentState) -> dict:
    messages = state["messages"]
    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}

def rag_node(state: AgentState) -> dict:
    last_msg = state["messages"][-1].content
    docs = retriever.invoke(last_msg)
    context = "\n".join([d.page_content for d in docs])
    return {"context": context}

def tool_node(state: AgentState) -> dict:
    last_message = state["messages"][-1]
    results = []
    for tool_call in last_message.tool_calls:
        if tool_call["name"] == "web_search":
            result = web_search.invoke(tool_call["args"]["query"])
            results.append(AIMessage(content=result, tool_call_id=tool_call["id"]))
    return {"messages": results}

def respond_node(state: AgentState) -> dict:
    context = state.get("context", "")
    messages = state["messages"]
    system_msg = SystemMessage(content=f"Tu es ELLIOTT, un assistant IA intelligent. Utilise le contexte quand disponible:\n{context}")
    response = llm.invoke([system_msg] + list(messages))
    return {"messages": [response]}

# =============================================================================
# ROUTING
# =============================================================================
def should_use_tool(state: AgentState) -> str:
    last_message = state["messages"][-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    return "respond"

# =============================================================================
# GRAPH
# =============================================================================
graph = StateGraph(AgentState)
graph.add_node("agent", agent_node)
graph.add_node("rag", rag_node)
graph.add_node("tools", tool_node)
graph.add_node("respond", respond_node)

graph.set_entry_point("rag")
graph.add_edge("rag", "agent")
graph.add_conditional_edges("agent", should_use_tool, {"tools": "tools", "respond": "respond"})
graph.add_edge("tools", "respond")
graph.add_edge("respond", END)

app_agent = graph.compile()

# =============================================================================
# FLASK APP
# =============================================================================
app = Flask(__name__)

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ELLIOTT - Agent IA Avance</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
:root{--bg:#09090b;--bgc:#18181b;--bgh:#27272a;--bd:#27272a;--tx:#fafafa;--txd:#a1a1aa;--ac:#f97316;--ach:#ea580c;--bl:#3b82f6;--gn:#22c55e;--r:12px}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:var(--bg);color:var(--tx);min-height:100vh;display:flex}
.sidebar{width:280px;background:var(--bgc);border-right:1px solid var(--bd);display:flex;flex-direction:column;height:100vh;position:fixed;left:0;top:0}
.sidebar-header{padding:24px;border-bottom:1px solid var(--bd)}
.logo{display:flex;align-items:center;gap:12px}
.logo-icon{width:48px;height:48px;background:linear-gradient(135deg,var(--ac),#fb923c);border-radius:12px;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:18px}
.logo-text{font-size:20px;font-weight:700;color:var(--ac)}
.logo-sub{font-size:12px;color:var(--txd)}
.menu{flex:1;padding:16px;overflow-y:auto}
.menu-title{font-size:11px;font-weight:600;color:var(--txd);text-transform:uppercase;letter-spacing:.5px;padding:8px 12px;margin-top:8px}
.menu-item{display:flex;align-items:center;gap:12px;padding:12px 16px;border-radius:var(--r);cursor:pointer;transition:all .15s;color:var(--txd);font-size:14px;font-weight:500}
.menu-item:hover{background:var(--bgh);color:var(--tx)}
.menu-item.active{background:var(--ac);color:#fff}
.menu-item svg{width:20px;height:20px;flex-shrink:0}
.sidebar-footer{padding:16px;border-top:1px solid var(--bd)}
.status{display:flex;align-items:center;gap:8px;font-size:13px;color:var(--gn)}
.status-dot{width:8px;height:8px;background:var(--gn);border-radius:50%;animation:pulse 2s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.5}}
.main{flex:1;margin-left:280px;display:flex;flex-direction:column;height:100vh}
.header{padding:16px 24px;border-bottom:1px solid var(--bd);display:flex;align-items:center;justify-content:space-between}
.header-title{font-size:16px;font-weight:600}
.header-actions{display:flex;gap:8px}
.header-btn{width:36px;height:36px;border-radius:8px;border:1px solid var(--bd);background:0 0;color:var(--txd);cursor:pointer;display:flex;align-items:center;justify-content:center;transition:all .15s}
.header-btn:hover{background:var(--bgh);color:var(--tx)}
.header-btn svg{width:18px;height:18px}
.chat{flex:1;overflow-y:auto;padding:24px;display:flex;flex-direction:column;gap:16px}
.message{display:flex;gap:12px;max-width:85%;animation:fadeIn .2s ease}
@keyframes fadeIn{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}
.message.user{align-self:flex-end;flex-direction:row-reverse}
.message-avatar{width:36px;height:36px;border-radius:10px;display:flex;align-items:center;justify-content:center;flex-shrink:0;font-size:14px;font-weight:600}
.message.user .message-avatar{background:var(--bl)}
.message.assistant .message-avatar{background:linear-gradient(135deg,var(--ac),#fb923c)}
.message-avatar svg{width:18px;height:18px}
.message-content{background:var(--bgc);padding:16px;border-radius:var(--r);line-height:1.6;font-size:14px;white-space:pre-wrap}
.message.user .message-content{background:var(--bl)}
.message-content strong{color:var(--ac)}
.message.user .message-content strong{color:#fff}
.message-content code{background:var(--bgh);padding:2px 6px;border-radius:4px;font-family:monospace;font-size:13px}
.message-content pre{background:var(--bgh);padding:12px;border-radius:8px;overflow-x:auto;margin:8px 0}
.message-content pre code{background:0 0;padding:0}
.suggestions{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}
.suggestion{padding:8px 14px;background:var(--bgh);border:1px solid var(--bd);border-radius:20px;font-size:13px;color:var(--tx);cursor:pointer;transition:all .15s}
.suggestion:hover{background:var(--ac);border-color:var(--ac)}
.input-container{padding:16px 24px 24px;background:var(--bg)}
.input-wrapper{display:flex;gap:8px;background:var(--bgc);border:1px solid var(--bd);border-radius:var(--r);padding:8px;transition:border-color .15s}
.input-wrapper:focus-within{border-color:var(--ac)}
.chat-input{flex:1;background:0 0;border:none;padding:12px 16px;color:var(--tx);font-size:15px;font-family:inherit;outline:0}
.chat-input::placeholder{color:var(--txd)}
.send-btn{width:44px;height:44px;border-radius:10px;border:none;background:var(--ac);color:#fff;cursor:pointer;display:flex;align-items:center;justify-content:center;transition:all .15s}
.send-btn:hover{background:var(--ach);transform:scale(1.05)}
.send-btn svg{width:20px;height:20px}
.typing{display:flex;gap:4px;padding:8px 16px}
.typing-dot{width:8px;height:8px;background:var(--ac);border-radius:50%;animation:typingBounce 1.4s infinite ease-in-out}
.typing-dot:nth-child(2){animation-delay:.2s}
.typing-dot:nth-child(3){animation-delay:.4s}
@keyframes typingBounce{0%,80%,100%{transform:scale(.6);opacity:.4}40%{transform:scale(1);opacity:1}}
.ai-badge{display:inline-flex;align-items:center;gap:4px;padding:2px 8px;background:var(--gn);color:#fff;border-radius:12px;font-size:10px;font-weight:600;margin-top:8px}
.welcome{text-align:center;padding:60px 24px;max-width:600px;margin:0 auto}
.welcome-icon{width:80px;height:80px;background:linear-gradient(135deg,var(--ac),#fb923c);border-radius:20px;display:flex;align-items:center;justify-content:center;margin:0 auto 24px}
.welcome-icon svg{width:40px;height:40px}
.welcome h2{font-size:24px;margin-bottom:8px}
.welcome p{color:var(--txd);margin-bottom:24px}
.welcome-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}
.welcome-card{background:var(--bgc);border:1px solid var(--bd);border-radius:var(--r);padding:20px 16px;cursor:pointer;transition:all .15s}
.welcome-card:hover{border-color:var(--ac);transform:translateY(-2px)}
.welcome-card-icon{width:40px;height:40px;background:var(--bgh);border-radius:10px;display:flex;align-items:center;justify-content:center;margin:0 auto 12px}
.welcome-card-icon svg{width:20px;height:20px;color:var(--ac)}
.welcome-card h4{font-size:14px;margin-bottom:4px}
.welcome-card p{font-size:12px;color:var(--txd);margin:0}
::-webkit-scrollbar{width:6px}
::-webkit-scrollbar-track{background:0 0}
::-webkit-scrollbar-thumb{background:var(--bd);border-radius:3px}
@media(max-width:768px){.sidebar{display:none}.main{margin-left:0}.message{max-width:90%}.welcome-grid{grid-template-columns:1fr}}
</style>
</head>
<body>
<aside class="sidebar">
<div class="sidebar-header">
<div class="logo">
<div class="logo-icon">E</div>
<div><div class="logo-text">ELLIOTT</div><div class="logo-sub">Agent IA Avance</div></div>
</div>
</div>
<nav class="menu">
<div class="menu-title">Agent</div>
<div class="menu-item active" onclick="selectMenu(this,'chat')">
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>Chat
</div>
<div class="menu-item" onclick="selectMenu(this,'search')">
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>Recherche Web
</div>
<div class="menu-item" onclick="selectMenu(this,'memory')">
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>Memoire RAG
</div>
<div class="menu-title">Fonctionnalites</div>
<div class="menu-item" onclick="sendQuick('Recherche les dernieres actualites IA')">
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>Actualites IA
</div>
<div class="menu-item" onclick="sendQuick('Explique LangGraph')">
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>LangGraph
</div>
</nav>
<div class="sidebar-footer">
<div class="status"><div class="status-dot"></div>LangGraph + RAG</div>
</div>
</aside>
<main class="main">
<header class="header">
<div class="header-title" id="headerTitle">Chat <span class="ai-badge">LangGraph + RAG</span></div>
<div class="header-actions">
<button class="header-btn" onclick="clearChat()" title="Nouvelle conversation">
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 5v14M5 12h14"/></svg>
</button>
</div>
</header>
<div class="chat" id="chatMessages">
<div class="welcome">
<div class="welcome-icon">
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>
</div>
<h2>Bonjour! Je suis ELLIOTT</h2>
<p>Agent IA avance propulse par <strong>LangGraph</strong> et <strong>RAG</strong>. Je peux rechercher sur le web et me souvenir de tout!</p>
<div class="welcome-grid">
<div class="welcome-card" onclick="sendQuick('Recherche les dernieres actualites sur l\\'intelligence artificielle')">
<div class="welcome-card-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg></div>
<h4>Actualites IA</h4><p>Recherche web</p>
</div>
<div class="welcome-card" onclick="sendQuick('Explique LangGraph et comment ca marche')">
<div class="welcome-card-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg></div>
<h4>LangGraph</h4><p>Comment ca marche?</p>
</div>
<div class="welcome-card" onclick="sendQuick('Ecris un script Python pour scraper un site web')">
<div class="welcome-card-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg></div>
<h4>Code</h4><p>Script Python</p>
</div>
<div class="welcome-card" onclick="sendQuick('Qu\\'est-ce que le RAG et comment ca marche?')">
<div class="welcome-card-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/></svg></div>
<h4>RAG</h4><p>Memoire longue</p>
</div>
</div>
</div>
</div>
<div class="input-container">
<div class="input-wrapper">
<input type="text" class="chat-input" id="chatInput" placeholder="Posez votre question..." maxlength="2000" onkeypress="if(event.key==='Enter')sendMessage()">
<button class="send-btn" onclick="sendMessage()">
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
</button>
</div>
</div>
</main>
<script>
var convId='c_'+Date.now();
function selectMenu(el,t){document.querySelectorAll('.menu-item').forEach(function(i){i.classList.remove('active')});el.classList.add('active');document.getElementById('headerTitle').innerHTML=el.textContent.trim()+' <span class="ai-badge">LangGraph + RAG</span>';}
function sendQuick(t){document.getElementById('chatInput').value=t;sendMessage();}
function addMessage(c,u,html){
var chat=document.getElementById('chatMessages');var w=chat.querySelector('.welcome');if(w)w.remove();
var m=document.createElement('div');m.className='message '+(u?'user':'assistant');
var a=u?'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z"/><path d="M8 14s1.5 2 4 2 4-2 4-2"/><line x1="9" y1="9" x2="9.01" y2="9"/><line x1="15" y1="9" x2="15.01" y2="9"/></svg>';
var content=html||c.replace(/\n/g,'<br>').replace(/\*\*(.*?)\*\*/g,'<strong>$1</strong>').replace(/```([\s\S]*?)```/g,'<pre><code>$1</code></pre>').replace(/`([^`]+)`/g,'<code>$1</code>');
var h='<div class="message-avatar">'+a+'</div><div class="message-content">'+content;
if(!u)h+='<div class="ai-badge">Propulse par LangGraph + RAG</div>';
h+='</div>';m.innerHTML=h;chat.appendChild(m);chat.scrollTop=chat.scrollHeight;}
function showTyping(){var chat=document.getElementById('chatMessages');var m=document.createElement('div');m.className='message assistant';m.id='typingMsg';m.innerHTML='<div class="message-avatar"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z"/><path d="M8 14s1.5 2 4 2 4-2 4-2"/><line x1="9" y1="9" x2="9.01" y2="9"/><line x1="15" y1="9" x2="15.01" y2="9"/></svg></div><div class="message-content"><div class="typing"><div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div></div></div>';chat.appendChild(m);chat.scrollTop=chat.scrollHeight;}
function hideTyping(){var t=document.getElementById('typingMsg');if(t)t.remove();}
async function sendMessage(){
var i=document.getElementById('chatInput');var msg=i.value.trim();if(!msg)return;
addMessage(msg,true);i.value='';showTyping();
try{var r=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:msg,conversation_id:convId})});var d=await r.json();hideTyping();addMessage(d.text||'Pas de reponse',false);}catch(e){hideTyping();addMessage('Erreur de connexion.',false);}
i.focus();}
function clearChat(){convId='c_'+Date.now();document.getElementById('chatMessages').innerHTML='<div class="welcome"><div class="welcome-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg></div><h2>Bonjour! Je suis ELLIOTT</h2><p>Agent IA avance propulse par <strong>LangGraph</strong> et <strong>RAG</strong>.</p><div class="welcome-grid"><div class="welcome-card" onclick="sendQuick(\'Recherche les actualites IA\')"><div class="welcome-card-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg></div><h4>Actualites</h4><p>Recherche web</p></div><div class="welcome-card" onclick="sendQuick(\'Explique LangGraph\')"><div class="welcome-card-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg></div><h4>LangGraph</h4><p>Comment ca marche?</p></div><div class="welcome-card" onclick="sendQuick(\'Ecris un script Python\')"><div class="welcome-card-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg></div><h4>Code</h4><p>Script</p></div><div class="welcome-card" onclick="sendQuick(\'Qu\\'est-ce que le RAG?\')"><div class="welcome-card-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/></svg></div><h4>RAG</h4><p>Memoire</p></div></div></div>';}
</script>
</body>
</html>"""

RENDERED_HTML = HTML_TEMPLATE.encode("utf-8")

@app.route("/")
def index():
    return Response(RENDERED_HTML, content_type="text/html; charset=utf-8")

@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True)
    if not data:
        return Response(b'{"error":"Invalid"}', status=400, content_type="application/json")
    message = data.get("message", "").strip()
    if not message:
        return Response(b'{"error":"Empty"}', status=400, content_type="application/json")
    
    try:
        result = app_agent.invoke({"messages": [HumanMessage(content=message)], "context": ""})
        response = result["messages"][-1].content
        resp = {"text": response, "fromAI": True}
    except Exception as e:
        resp = {"text": f"Erreur: {str(e)}", "fromAI": False}
    
    body = _json.dumps(resp, ensure_ascii=False).encode("utf-8")
    return Response(body, content_type="application/json; charset=utf-8")

if __name__ == "__main__":
    print("=" * 50)
    print("  ELLIOTT - Agent IA Avance")
    print("  http://localhost:5000")
    print("  LangGraph + RAG + Recherche Web")
    print("=" * 50)
    app.run(debug=False, host="127.0.0.1", port=5000, threaded=True)
