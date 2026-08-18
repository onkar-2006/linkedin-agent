import React, { useState, useEffect, useRef } from 'react';
import { 
  Send, Plus, Trash2, Calendar, CheckCircle2, Clock, X, 
  Linkedin, Search, Sparkles, Image as ImageIcon, ChevronDown, 
  ChevronUp, AlertCircle, LogOut, ArrowRight, UserCheck, AlertTriangle
} from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000/api';

export default function App() {
  const [conversations, setConversations] = useState([]);
  const [activeConversationId, setActiveConversationId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [inputText, setInputText] = useState('');
  const [posts, setPosts] = useState([]);
  const [linkedinStatus, setLinkedinStatus] = useState({ connected: false });
  const [isLoading, setIsLoading] = useState(false);
  const [collapsedThinking, setCollapsedThinking] = useState({});
  const [showScheduleModal, setShowScheduleModal] = useState(false);
  const [selectedDraftText, setSelectedDraftText] = useState('');
  const [selectedImage, setSelectedImage] = useState('');
  const [scheduleTime, setScheduleTime] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [generatingImageId, setGeneratingImageId] = useState(null);
  const [errorMsg, setErrorMsg] = useState('');

  // Human-in-the-loop workflow state
  const [graphState, setGraphState] = useState(null);
  const [revisionText, setRevisionText] = useState('');
  const [showRevisionInput, setShowRevisionInput] = useState(false);
  const [selectedScheduleTime, setSelectedScheduleTime] = useState('');
  const [showSidebar, setShowSidebar] = useState(true);

  const [activeUserUrn, setActiveUserUrn] = useState(localStorage.getItem('activeUserUrn') || '');
  const messagesEndRef = useRef(null);

  // Helper function to dynamically inject active user session headers
  const fetchWithAuth = (url, options = {}) => {
    const headers = { ...options.headers };
    if (activeUserUrn) {
      headers['X-User-URN'] = activeUserUrn;
    }
    return fetch(url, { ...options, headers });
  };

  // Parse URN credentials on callback redirection
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get('auth') === 'success') {
      const urn = params.get('urn');
      if (urn) {
        localStorage.setItem('activeUserUrn', urn);
        setActiveUserUrn(urn);
      }
      // Strip credentials from address bar
      window.history.replaceState({}, document.title, window.location.pathname);
    }
  }, []);

  // Initialize and reload data when active user changes
  useEffect(() => {
    fetchConversations();
    fetchPosts();
    fetchLinkedinStatus();
  }, [activeUserUrn]);

  // Fetch conversations history
  const fetchConversations = async () => {
    try {
      const res = await fetchWithAuth(`${API_BASE}/conversations`);
      if (res.ok) {
        const data = await res.json();
        setConversations(data);
        if (data.length > 0 && !activeConversationId) {
          selectConversation(data[0].id);
        }
      }
    } catch (err) {
      console.error("Error fetching conversations:", err);
    }
  };

  // Fetch LinkedIn connection status
  const fetchLinkedinStatus = async () => {
    try {
      const res = await fetchWithAuth(`${API_BASE}/auth/linkedin/status`);
      if (res.ok) {
        const data = await res.json();
        setLinkedinStatus(data);
      }
    } catch (err) {
      console.error("Error fetching LinkedIn status:", err);
    }
  };

  // Fetch posts from database
  const fetchPosts = async () => {
    try {
      const res = await fetchWithAuth(`${API_BASE}/posts`);
      if (res.ok) {
        const data = await res.json();
        setPosts(data);
      }
    } catch (err) {
      console.error("Error fetching posts:", err);
    }
  };

  // Select a conversation and load messages
  const selectConversation = async (id) => {
    setActiveConversationId(id);
    try {
      const res = await fetchWithAuth(`${API_BASE}/conversations/${id}/messages`);
      if (res.ok) {
        const data = await res.json();
        setMessages(data.messages || []);
        setGraphState(data.graph_state || null);
      }
    } catch (err) {
      console.error("Error loading messages:", err);
    }
  };

  // Start a new conversation
  const startNewChat = () => {
    setActiveConversationId(null);
    setMessages([]);
    setGraphState(null);
    setInputText('');
  };

  // Connect to LinkedIn OAuth
  const connectLinkedIn = async () => {
    try {
      const res = await fetchWithAuth(`${API_BASE}/auth/linkedin`);
      const data = await res.json();
      if (data.url) {
        window.location.href = data.url;
      } else {
        alert(data.message || "Could not start authorization.");
      }
    } catch (err) {
      console.error("OAuth init failed:", err);
    }
  };

  // Disconnect from LinkedIn
  const disconnectLinkedIn = async () => {
    try {
      await fetchWithAuth(`${API_BASE}/auth/linkedin/disconnect`, { method: 'POST' });
      localStorage.removeItem('activeUserUrn');
      setActiveUserUrn('');
      setLinkedinStatus({ connected: false });
    } catch (err) {
      console.error("Disconnect failed:", err);
    }
  };

  // Delete a post
  const deletePost = async (id) => {
    try {
      const res = await fetchWithAuth(`${API_BASE}/posts/${id}`, { method: 'DELETE' });
      if (res.ok) {
        fetchPosts();
      }
    } catch (err) {
      console.error("Delete post failed:", err);
    }
  };

  // Delete a conversation
  const deleteConversation = async (id, e) => {
    e.stopPropagation();
    try {
      const res = await fetchWithAuth(`${API_BASE}/conversations/${id}`, { method: 'DELETE' });
      if (res.ok) {
        fetchConversations();
        if (activeConversationId === id) {
          startNewChat();
        }
      }
    } catch (err) {
      console.error("Delete conversation failed:", err);
    }
  };

  // Submit chat prompt to backend
  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!inputText.trim() || isLoading) return;

    setErrorMsg('');
    const userMsgText = inputText;
    setInputText('');
    setIsLoading(true);

    // Optimistic user message render
    const tempUserMsg = { role: 'user', content: userMsgText };
    setMessages(prev => [...prev, tempUserMsg]);

    try {
      const res = await fetchWithAuth(`${API_BASE}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: userMsgText,
          conversation_id: activeConversationId
        })
      });

      if (!res.ok) throw new Error("Backend connection failed.");
      const data = await res.json();

      if (!activeConversationId) {
        setActiveConversationId(data.conversation_id);
        fetchConversations();
      }

      // Refresh messages
      selectConversation(data.conversation_id);
    } catch (err) {
      console.error("Chat error:", err);
      setErrorMsg("Failed to connect or get response from agent server.");
    } finally {
      setIsLoading(false);
    }
  };

  // Submit state updates and run the graph state machine
  const updateAgentState = async (stateUpdate, userMsgText = "") => {
    if (isLoading) return;
    setErrorMsg('');
    setIsLoading(true);
    
    if (userMsgText) {
      setMessages(prev => [...prev, { role: 'user', content: userMsgText }]);
    }
    
    try {
      const res = await fetchWithAuth(`${API_BASE}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: userMsgText,
          conversation_id: activeConversationId,
          state_update: stateUpdate
        })
      });
      
      if (!res.ok) throw new Error("Connection failed");
      const data = await res.json();
      
      if (!activeConversationId) {
        setActiveConversationId(data.conversation_id);
        fetchConversations();
      }
      
      // Update UI state with returned result
      setGraphState(data.graph_state);
      selectConversation(data.conversation_id);
      fetchPosts(); // Refresh post schedule list
    } catch (err) {
      console.error(err);
      setErrorMsg("Failed to communicate with stateful agent.");
    } finally {
      setIsLoading(false);
    }
  };

  // Generate Image for a draft post
  const generateDraftImage = async (msgId, text) => {
    setGeneratingImageId(msgId);
    try {
      const res = await fetchWithAuth(`${API_BASE}/agent/generate-image`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message_id: msgId, draft_text: text })
      });
      if (res.ok) {
        if (activeConversationId) {
          selectConversation(activeConversationId);
        }
      } else {
        alert("Failed to generate image.");
      }
    } catch (err) {
      console.error(err);
    } finally {
      setGeneratingImageId(null);
    }
  };

  // Publish a draft post immediately
  const publishImmediately = async (text, imgUrl) => {
    if (!linkedinStatus.connected) {
      alert("Please connect your LinkedIn account first using the button in the top left!");
      return;
    }
    
    try {
      const res = await fetchWithAuth(`${API_BASE}/posts/publish`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, image_url: imgUrl })
      });
      const data = await res.json();
      alert(data.message);
      fetchPosts();
    } catch (err) {
      console.error(err);
      alert("Failed to publish post.");
    }
  };

  // Open scheduling modal
  const openScheduleModal = (text, imgUrl) => {
    setSelectedDraftText(text);
    setSelectedImage(imgUrl);
    setScheduleTime('');
    setShowScheduleModal(true);
  };

  // Confirm schedule
  const confirmSchedule = async () => {
    if (!scheduleTime) return;
    if (!linkedinStatus.connected) {
      alert("Please connect your LinkedIn account first using the button in the top left!");
      return;
    }

    try {
      const res = await fetchWithAuth(`${API_BASE}/posts/schedule`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text: selectedDraftText,
          image_url: selectedImage,
          publish_time: scheduleTime
        })
      });
      const data = await res.json();
      if (res.ok) {
        alert(data.message);
        setShowScheduleModal(false);
        fetchPosts();
      } else {
        alert(data.detail || "Failed to schedule post.");
      }
    } catch (err) {
      console.error(err);
      alert("Scheduling request failed.");
    }
  };

  // Scroll to bottom helper
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  const toggleThinking = (index) => {
    setCollapsedThinking(prev => ({
      ...prev,
      [index]: !prev[index]
    }));
  };

  const filteredConversations = conversations.filter(c => 
    c.title && c.title.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-slate-950 text-slate-100">
      
      {/* 1. LEFT SIDEBAR (COLLAPSIBLE HISTORY PANEL) */}
      {showSidebar && (
        <aside className="w-80 border-r border-slate-800 bg-gradient-to-b from-slate-900 via-slate-900 to-slate-950 flex flex-col h-full z-10 transition-all duration-300 shadow-xl">
          {/* Sidebar Header */}
          <div className="p-4 border-b border-slate-800/80 flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="bg-gradient-to-tr from-blue-600 to-indigo-600 p-1.5 rounded-lg text-white shadow-md shadow-blue-500/20">
                  <Linkedin className="h-5 w-5" />
                </div>
                <div>
                  <h1 className="font-bold text-sm leading-tight tracking-wide bg-gradient-to-r from-white to-slate-300 bg-clip-text text-transparent">Linkedin Agent</h1>
                  <span className="text-[10px] text-slate-400 font-medium">Autopilot Scheduler</span>
                </div>
              </div>
              <button 
                onClick={() => setShowSidebar(false)}
                className="p-1.5 hover:bg-slate-800 rounded-lg text-slate-400 hover:text-slate-200 transition-all"
                title="Collapse Sidebar"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {/* LinkedIn Connection Status */}
            {linkedinStatus.connected ? (
              <div className="flex items-center justify-between bg-slate-800/40 p-2.5 rounded-xl border border-emerald-500/20 backdrop-blur-sm shadow-inner transition-all duration-300">
                <div className="flex items-center gap-2 min-w-0">
                  {linkedinStatus.profile_picture ? (
                    <img src={linkedinStatus.profile_picture} alt="Avatar" className="w-8 h-8 rounded-full object-cover border-2 border-emerald-500 shadow" />
                  ) : (
                    <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-white font-bold border-2 border-emerald-500 shadow">
                      {linkedinStatus.first_name?.[0]}
                    </div>
                  )}
                  <div className="min-w-0">
                    <p className="text-xs font-semibold truncate leading-none text-slate-200">{linkedinStatus.first_name} {linkedinStatus.last_name}</p>
                    <span className="text-[10px] text-emerald-400 flex items-center gap-0.5 mt-1 font-medium">
                      <UserCheck className="h-3 w-3 animate-pulse" /> Connected
                    </span>
                  </div>
                </div>
                <button onClick={disconnectLinkedIn} title="Disconnect LinkedIn" className="p-1.5 text-slate-400 hover:text-rose-400 hover:bg-slate-800/50 rounded-md transition-all">
                  <LogOut className="h-4 w-4" />
                </button>
              </div>
            ) : (
              <button 
                onClick={connectLinkedIn}
                className="flex items-center justify-center gap-2 w-full bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 active:scale-[0.98] transition-all py-2 px-3 rounded-xl text-sm font-semibold text-white shadow-lg shadow-blue-900/30 hover:shadow-blue-500/10 cursor-pointer"
              >
                <Linkedin className="h-4 w-4" /> Connect LinkedIn
              </button>
            )}

            {/* New Chat Button */}
            <button 
              onClick={startNewChat}
              className="flex items-center justify-center gap-2 w-full border border-slate-700/80 hover:border-slate-500 hover:bg-slate-800/60 active:scale-[0.98] transition-all py-2 px-3 rounded-xl text-sm font-medium text-slate-200 cursor-pointer"
            >
              <Plus className="h-4 w-4 text-blue-500" /> New Chat
            </button>
          </div>

          {/* Sidebar Navigation Panels */}
          <div className="flex-1 overflow-y-auto p-3 flex flex-col gap-4">
            
            {/* History Search */}
            <div className="relative">
              <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-slate-500" />
              <input 
                type="text" 
                placeholder="Search chats..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded-md pl-9 pr-3 py-2 text-xs text-slate-300 placeholder-slate-500 focus:outline-none focus:border-slate-700"
              />
            </div>

            {/* Conversations History List */}
            <div>
              <span className="text-[10px] font-bold tracking-wider text-slate-500 uppercase px-2">History</span>
              <div className="flex flex-col gap-1 mt-2">
                {filteredConversations.length === 0 ? (
                  <p className="text-xs text-slate-500 px-2 py-1">No chats found.</p>
                ) : (
                  filteredConversations.map(c => (
                    <div 
                      key={c.id}
                      onClick={() => selectConversation(c.id)}
                      className={`flex items-center justify-between p-2 rounded-lg text-xs cursor-pointer group transition-colors ${
                        activeConversationId === c.id 
                          ? 'bg-slate-800 text-white font-medium border-l-2 border-blue-500' 
                          : 'text-slate-400 hover:bg-slate-800/50 hover:text-slate-200'
                      }`}
                    >
                      <span className="truncate flex-1 pr-2">{c.title || "Untitled Conversation"}</span>
                      <button 
                        onClick={(e) => deleteConversation(c.id, e)}
                        className="opacity-0 group-hover:opacity-100 p-0.5 text-slate-500 hover:text-rose-400 transition-opacity"
                      >
                        <Trash2 className="h-3 w-3" />
                      </button>
                    </div>
                  ))
                )}
              </div>
            </div>

            <hr className="border-slate-800" />

            {/* LinkedIn Live Feed status / Scheduled Posts */}
            <div>
              <span className="text-[10px] font-bold tracking-wider text-slate-500 uppercase px-2">LinkedIn Posts Status</span>
              <div className="flex flex-col gap-2 mt-2">
                {posts.length === 0 ? (
                  <p className="text-xs text-slate-500 px-2 py-1">No posts scheduled or published.</p>
                ) : (
                  posts.map(post => (
                    <div key={post.id} className="bg-slate-950 p-2.5 rounded-lg border border-slate-800 text-xs flex flex-col gap-1.5 group">
                      <div className="flex items-center justify-between">
                        <span className={`inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-full ${
                          post.status === 'published' 
                            ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' 
                            : post.status === 'scheduled'
                            ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                            : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                        }`}>
                          {post.status === 'published' ? <CheckCircle2 className="h-3 w-3" /> : <Clock className="h-3 w-3" />}
                          {post.status.toUpperCase()}
                        </span>
                        <button 
                          onClick={() => deletePost(post.id)}
                          className="opacity-0 group-hover:opacity-100 text-slate-500 hover:text-rose-400 transition-opacity"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </div>
                      
                      <p className="text-slate-300 line-clamp-2 leading-relaxed">{post.content}</p>
                      
                      {post.image_url && (
                        <div className="h-10 rounded overflow-hidden mt-0.5">
                          <img src={post.image_url} alt="Post preview" className="w-full h-full object-cover opacity-60" />
                        </div>
                      )}
                      
                      {post.status === 'scheduled' && post.scheduled_time && (
                        <div className="text-[10px] text-slate-400 flex items-center gap-1 mt-0.5">
                          <Calendar className="h-3 w-3" /> {new Date(post.scheduled_time).toLocaleString()}
                        </div>
                      )}
                    </div>
                  ))
                )}
              </div>
            </div>

          </div>
        </aside>
      )}

      {/* 2. MAIN SPLIT-PANE DASHBOARD */}
      <main className="flex-1 flex flex-col h-full bg-slate-950 relative">
        
        {/* Chat Area Header */}
        <header className="h-16 border-b border-slate-800/80 px-6 flex items-center justify-between bg-slate-900/40 backdrop-blur-md z-10">
          <div className="flex items-center gap-4">
            {!showSidebar && (
              <button 
                onClick={() => setShowSidebar(true)}
                className="p-2 bg-slate-800/80 hover:bg-slate-700 hover:text-white rounded-xl text-slate-300 transition-all active:scale-95 shadow-md shadow-black/10 cursor-pointer"
                title="Expand History Sidebar"
              >
                <Plus className="h-4 w-4" />
              </button>
            )}
            <div className="flex items-center gap-2">
              <Sparkles className="h-5 w-5 text-blue-500 animate-pulse" />
              <h2 className="font-semibold text-sm tracking-wide">
                {activeConversationId 
                  ? conversations.find(c => c.id === activeConversationId)?.title || "Active Discussion"
                  : "New Autopilot Draft"}
              </h2>
            </div>
          </div>
          <div className="text-xs text-slate-400 flex items-center gap-1.5 bg-slate-900/30 px-3 py-1.5 rounded-full border border-slate-800/50">
            <span className={`w-2 h-2 rounded-full ${linkedinStatus.connected ? 'bg-emerald-500 shadow-md shadow-emerald-500/50' : 'bg-amber-500 animate-pulse'}`}></span>
            <span className="font-medium text-[11px]">{linkedinStatus.connected ? 'API Live Connection' : 'API Connection Needed'}</span>
          </div>
        </header>

        {/* SPLIT PANE BODY */}
        <div className="flex-1 flex overflow-hidden">
          
          {/* LEFT PANEL: User-Agent dialogue log & prompt input */}
          <div className="flex-1 flex flex-col h-full border-r border-slate-800/80 bg-slate-950/20 overflow-hidden">
            <div className="flex-1 overflow-y-auto p-6 space-y-6">
              {messages.length === 0 && (
                <div className="max-w-xl mx-auto text-center py-20 flex flex-col items-center justify-center gap-5 animate-fadein">
                  <div className="w-16 h-16 bg-blue-600/10 text-blue-500 rounded-2xl flex items-center justify-center border border-blue-500/20 shadow-lg shadow-blue-500/5 animate-float">
                    <Sparkles className="h-8 w-8" />
                  </div>
                  <div>
                    <h3 className="text-lg font-bold tracking-wide">Welcome to LinkedIn Post Autopilot</h3>
                    <p className="text-sm text-slate-400 mt-2 max-w-sm leading-relaxed">
                      Send a topic or trending idea, and I will search the web, draft the perfect copy, generate a high-quality graphic, and schedule it to your LinkedIn feed.
                    </p>
                  </div>
                  <div className="grid grid-cols-2 gap-3 w-full max-w-md mt-6">
                    <button 
                      onClick={() => setInputText("Draft a post explaining the release of Vite 6.0")}
                      className="bg-slate-900/60 hover:bg-slate-800/80 border border-slate-800 hover:border-slate-700/80 transition-all rounded-xl p-4 text-xs text-left cursor-pointer hover:shadow-lg shadow-black/10"
                    >
                      "Explain Vite 6.0 release..."
                    </button>
                    <button 
                      onClick={() => setInputText("Write a promotional post for a remote startup hiring React developers")}
                      className="bg-slate-900/60 hover:bg-slate-800/80 border border-slate-800 hover:border-slate-700/80 transition-all rounded-xl p-4 text-xs text-left cursor-pointer hover:shadow-lg shadow-black/10"
                    >
                      "React recruitment post..."
                    </button>
                  </div>
                </div>
              )}

              {messages.map((msg, index) => (
                <div key={index} className={`flex flex-col gap-2 max-w-2xl animate-slideup ${msg.role === 'user' ? 'ml-auto' : 'mr-auto'}`}>
                  <div className={`p-4 rounded-2xl text-sm leading-relaxed border shadow-sm ${
                    msg.role === 'user' 
                      ? 'bg-blue-600/15 border-blue-500/20 text-slate-200' 
                      : 'bg-slate-900/50 border-slate-800/80 text-slate-300'
                  }`}>
                    {/* Collapsible Thinking Process inside chat messages */}
                    {msg.role === 'assistant' && msg.thinking && (
                      <div className="bg-slate-950 border border-slate-800 rounded-xl overflow-hidden mb-3">
                        <button 
                          onClick={() => toggleThinking(index)}
                          className="flex items-center justify-between w-full px-3 py-2 text-xs font-semibold text-slate-400 hover:bg-slate-850/50 transition-colors"
                        >
                          <span className="flex items-center gap-1.5">
                            <Search className="h-3.5 w-3.5 text-blue-400" /> Agent Research & Thinking Log
                          </span>
                          {collapsedThinking[index] ? <ChevronDown className="h-4 w-4" /> : <ChevronUp className="h-4 w-4" />}
                        </button>
                        
                        {!collapsedThinking[index] && (
                          <div className="p-3 border-t border-slate-850 text-xs text-slate-400 font-mono whitespace-pre-line leading-relaxed max-h-48 overflow-y-auto">
                            {msg.thinking}
                          </div>
                        )}
                      </div>
                    )}
                    <p className="whitespace-pre-line">{msg.content}</p>
                    {msg.image_url && (
                      <div className="mt-3 rounded-xl overflow-hidden border border-slate-800 max-h-60 shadow-md">
                        <img src={msg.image_url} alt="Generated visual preview" className="w-full object-cover" />
                      </div>
                    )}
                  </div>
                </div>
              ))}

              {/* Loading Indicator */}
              {isLoading && (
                <div className="flex flex-col gap-2 max-w-xl mr-auto animate-pulse">
                  <div className="bg-slate-900/60 border border-slate-850 p-4 rounded-2xl flex items-center gap-3">
                    <div className="w-5 h-5 border-2 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
                    <span className="text-xs text-slate-400">Agent is performing search and compiling professional draft...</span>
                  </div>
                </div>
              )}

              {errorMsg && (
                <div className="bg-rose-500/10 border border-rose-500/20 text-rose-400 p-4 rounded-2xl text-xs flex items-center gap-2 max-w-xl">
                  <AlertCircle className="h-4 w-4" /> {errorMsg}
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>

            {/* Bottom Message Input bar */}
            <footer className="p-4 border-t border-slate-800/80 bg-slate-950/40 backdrop-blur-md">
              <form onSubmit={handleSendMessage} className="max-w-3xl mx-auto flex items-center gap-3">
                <input 
                  type="text" 
                  value={inputText}
                  onChange={(e) => setInputText(e.target.value)}
                  placeholder={linkedinStatus.connected ? "Ask agent to write a post..." : "Connect LinkedIn first, then ask agent to write..."}
                  className="flex-1 bg-slate-900/50 border border-slate-800 hover:border-slate-700/80 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 rounded-xl px-4 py-3 text-sm placeholder-slate-500 focus:outline-none transition-all text-slate-100 shadow-inner"
                />
                <button 
                  type="submit"
                  disabled={isLoading || !inputText.trim()}
                  className="bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 active:scale-95 disabled:bg-slate-800 text-white rounded-xl p-3 shadow-md shadow-blue-900/20 transition-all cursor-pointer"
                >
                  <Send className="h-4 w-4" />
                </button>
              </form>
            </footer>
          </div>

          {/* RIGHT PANEL: Agent Generated Content & Stateful Approvals Workspace */}
          <div className="w-[50%] flex flex-col h-full bg-slate-900/40 border-l border-slate-800/80 overflow-y-auto p-6 space-y-6">
            <div className="border-b border-slate-800 pb-3 flex flex-col">
              <h3 className="font-bold text-sm text-blue-400 flex items-center gap-2">
                <Sparkles className="h-4 w-4" /> Agent Workspace
              </h3>
              <p className="text-[10px] text-slate-400">Review generated draft copywriting and visual graphics here.</p>
            </div>

            {/* 1. Post Content Draft Preview */}
            {graphState && graphState.draft_content ? (
              <div className="glass-card rounded-2xl p-5 flex flex-col gap-3 animate-fadein">
                <span className="text-[10px] font-bold tracking-wider text-slate-500 uppercase">Latest Copy Draft</span>
                <p className="whitespace-pre-line text-sm text-slate-200 leading-relaxed font-sans select-all selection:bg-blue-600/40">
                  {graphState.draft_content}
                </p>
              </div>
            ) : (
              <div className="flex-1 flex flex-col items-center justify-center text-center p-10 text-slate-500 border border-dashed border-slate-800 rounded-2xl animate-fadein">
                <Sparkles className="h-8 w-8 mb-2 opacity-50 text-slate-500 animate-float" />
                <p className="text-xs">No active copywriting draft yet. Submit a prompt in the chat to begin!</p>
              </div>
            )}

            {/* 2. Bound Visual Image Preview */}
            {graphState && graphState.image_url && (
              <div className="glass-card rounded-2xl p-5 flex flex-col gap-3 animate-fadein">
                <span className="text-[10px] font-bold tracking-wider text-slate-500 uppercase">Bound Graphic</span>
                <div className="rounded-xl overflow-hidden border border-slate-800 max-h-64 shadow-md">
                  <img src={graphState.image_url} alt="Draft Graphic" className="w-full object-cover transition-transform hover:scale-105 duration-500" />
                </div>
              </div>
            )}

            {/* 3. Interactive flow controls inside workspace */}
            {graphState && graphState.next && graphState.next.length > 0 && !isLoading && (
              <div className="glass-card border border-blue-500/20 rounded-2xl p-5 shadow-2xl flex flex-col gap-4 animate-fadein">
                
                {/* Node 1: research_and_draft interrupt (Human draft review) */}
                {graphState.next.includes("wait_draft_approval") && (
                  <div className="flex flex-col gap-3">
                    <div className="flex items-center gap-2 text-blue-400 font-semibold text-sm">
                      <Sparkles className="h-4 w-4" /> Review the Draft LinkedIn Post
                    </div>
                    <p className="text-xs text-slate-300">
                      Please approve the draft to proceed, or write change instructions below.
                    </p>
                    
                    {showRevisionInput ? (
                      <div className="flex flex-col gap-2 mt-2">
                        <textarea
                          value={revisionText}
                          onChange={(e) => setRevisionText(e.target.value)}
                          placeholder="Explain what you want changed in the draft..."
                          className="w-full bg-slate-900/60 border border-slate-800 focus:border-blue-500 focus:ring-1 focus:ring-blue-500/25 rounded-xl p-2.5 text-xs text-slate-200 focus:outline-none"
                          rows={3}
                        />
                        <div className="flex gap-2">
                          <button
                            onClick={() => {
                              if (revisionText.trim()) {
                                updateAgentState({ approval_status: "revision_requested" }, revisionText);
                                setRevisionText('');
                                setShowRevisionInput(false);
                              }
                            }}
                            className="px-3 py-1.5 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-550 hover:to-indigo-550 text-white rounded-lg text-xs font-semibold hover:scale-[1.01] active:scale-[0.99] transition-all cursor-pointer"
                          >
                            Submit Revision Request
                          </button>
                          <button
                            onClick={() => setShowRevisionInput(false)}
                            className="px-3 py-1.5 border border-slate-700 hover:bg-slate-800 rounded-lg text-xs text-slate-300 transition-all cursor-pointer"
                          >
                            Cancel
                          </button>
                        </div>
                      </div>
                    ) : (
                      <div className="flex gap-3 mt-1">
                        <button
                          onClick={() => updateAgentState({ approval_status: "approved" })}
                          className="px-4 py-2 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 rounded-lg text-xs font-semibold text-white hover:scale-[1.01] active:scale-[0.99] transition-all cursor-pointer shadow-md shadow-emerald-950/20"
                        >
                          Approve Draft
                        </button>
                        <button
                          onClick={() => setShowRevisionInput(true)}
                          className="px-4 py-2 bg-slate-800 hover:bg-slate-750 rounded-lg text-xs font-semibold text-slate-300 transition-all cursor-pointer"
                        >
                          Request Revision
                        </button>
                      </div>
                    )}
                  </div>
                )}

                {/* Node 2: ask_image_option interrupt (Image generation prompt) */}
                {graphState.next.includes("wait_image_choice") && (
                  <div className="flex flex-col gap-3">
                    <div className="flex items-center gap-2 text-indigo-400 font-semibold text-sm">
                      <ImageIcon className="h-4 w-4 animate-bounce" /> Add Visual Graphic/Image?
                    </div>
                    <p className="text-xs text-slate-300">
                      Would you like the AI image generation agent to create a customized professional graphic for this post?
                    </p>
                    <div className="flex gap-3 mt-1">
                      <button
                        onClick={() => updateAgentState({ image_needed: "yes" })}
                        className="px-4 py-2 bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 rounded-lg text-xs font-semibold text-white hover:scale-[1.01] active:scale-[0.99] transition-all cursor-pointer shadow-md"
                      >
                        Yes, Generate Image
                      </button>
                      <button
                        onClick={() => updateAgentState({ image_needed: "no" })}
                        className="px-4 py-2 bg-slate-800 hover:bg-slate-750 rounded-lg text-xs font-semibold text-slate-300 transition-all cursor-pointer"
                      >
                        No, Text Only
                      </button>
                    </div>
                  </div>
                )}

                {/* Node 3: generate_image interrupt (Image approval review) */}
                {graphState.next.includes("wait_image_approval") && (
                  <div className="flex flex-col gap-3">
                    <div className="flex items-center gap-2 text-indigo-400 font-semibold text-sm">
                      <CheckCircle2 className="h-4 w-4 text-emerald-400 animate-pulse" /> Review Generated Graphic
                    </div>
                    <p className="text-xs text-slate-300">
                      Does this visual graphic look good, or should we recreate it?
                    </p>
                    <div className="flex gap-3 mt-1">
                      <button
                        onClick={() => updateAgentState({ image_approved: "yes" })}
                        className="px-4 py-2 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 rounded-lg text-xs font-semibold text-white hover:scale-[1.01] active:scale-[0.99] transition-all cursor-pointer"
                      >
                        Approve & Proceed
                      </button>
                      <button
                        onClick={() => updateAgentState({ image_approved: "no" })}
                        className="px-4 py-2 bg-slate-800 hover:bg-slate-755 rounded-lg text-xs font-semibold text-slate-300 transition-all cursor-pointer"
                      >
                        Regenerate Image
                      </button>
                    </div>
                  </div>
                )}

                {/* Node 4: posting_agent interrupt (Select schedule or immediate) */}
                {graphState.next.includes("wait_post_mode") && (
                  <div className="flex flex-col gap-3">
                    <div className="flex items-center gap-2 text-amber-500 font-semibold text-sm">
                      <Clock className="h-4 w-4" /> Select Posting Mode
                    </div>
                    <p className="text-xs text-slate-300">
                      Your post copywriting and visual are fully optimized. Choose when to post:
                    </p>
                    
                    <div className="flex flex-col gap-3 mt-1">
                      <div className="flex gap-2">
                        <button
                          onClick={() => updateAgentState({ post_mode: "immediate" })}
                          className="px-4 py-2 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 rounded-lg text-xs font-semibold text-white hover:scale-[1.01] active:scale-[0.99] transition-all cursor-pointer shadow-md"
                        >
                          Publish Immediately
                        </button>
                      </div>
                      
                      <div className="border-t border-slate-800 pt-3 flex flex-col gap-2">
                        <span className="text-[10px] text-slate-400 font-bold uppercase">Or Schedule for Future:</span>
                        <div className="flex gap-2 items-center">
                          <input
                            type="datetime-local"
                            value={selectedScheduleTime}
                            onChange={(e) => setSelectedScheduleTime(e.target.value)}
                            className="bg-slate-950 border border-slate-800 rounded-lg p-2 text-xs text-slate-200 focus:outline-none"
                          />
                          <button
                            disabled={!selectedScheduleTime}
                            onClick={() => {
                              updateAgentState({ post_mode: "scheduled", scheduled_time: selectedScheduleTime });
                              setSelectedScheduleTime('');
                            }}
                            className="px-3 py-2 bg-amber-600 hover:bg-amber-500 disabled:bg-slate-800 rounded-lg text-xs font-semibold text-white hover:scale-[1.01] transition-all cursor-pointer"
                          >
                            Schedule
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                {/* Node 5: confirm_posting_prompt interrupt (Safety check / confirm immediate) */}
                {graphState.next.includes("wait_post_confirmation") && (
                  <div className="flex flex-col gap-3">
                    <div className="flex items-center gap-2 text-rose-500 font-semibold text-sm">
                      <AlertTriangle className="h-4 w-4 text-rose-500 animate-pulse" /> Final LinkedIn Publish Confirmation
                    </div>
                    <p className="text-xs text-slate-300 font-medium">
                      We are ready to publish this post immediately to your connected LinkedIn profile. Confirm to post.
                    </p>
                    <div className="flex gap-3 mt-1">
                      <button
                        onClick={() => updateAgentState({ post_confirmed: "yes" })}
                        className="px-4 py-2 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 rounded-lg text-xs font-semibold text-white hover:scale-[1.01] active:scale-[0.99] transition-all cursor-pointer"
                      >
                        Yes, Publish Now
                      </button>
                      <button
                        onClick={() => updateAgentState({ post_confirmed: "no" })}
                        className="px-4 py-2 bg-slate-800 hover:bg-slate-750 rounded-lg text-xs font-semibold text-slate-300 transition-all cursor-pointer"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                )}

              </div>
            )}

            {/* 4. Posting Result status */}
            {graphState && graphState.posting_result && (
              <div className="bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 p-4 rounded-xl text-xs leading-relaxed mt-4 animate-fadein">
                <CheckCircle2 className="h-4 w-4 inline mr-2" /> {graphState.posting_result}
              </div>
            )}
          </div>

        </div>

      </main>

      {/* 3. SCHEDULING MODAL DIALOG */}
      {showScheduleModal && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="bg-slate-900 border border-slate-800 rounded-xl max-w-md w-full p-6 shadow-2xl flex flex-col gap-4">
            
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="text-sm font-bold flex items-center gap-2">
                <Calendar className="h-4 w-4 text-amber-500" /> Schedule Post Publication
              </h3>
              <button onClick={() => setShowScheduleModal(false)} className="text-slate-400 hover:text-slate-200">
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-[10px] font-bold text-slate-500 uppercase">Target Date & Time</label>
              <input 
                type="datetime-local" 
                value={scheduleTime}
                onChange={(e) => setScheduleTime(e.target.value)}
                className="bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-sm text-slate-200 focus:outline-none focus:border-slate-700"
              />
            </div>

            <div className="bg-amber-500/10 border border-amber-500/20 rounded-lg p-3 text-xs text-amber-400 flex gap-2">
              <AlertTriangle className="h-4 w-4 flex-shrink-0" />
              <p className="leading-relaxed">
                Ensure your LinkedIn login is active. The backend scheduler worker thread will automatically invoke the LinkedIn API once the target time is reached.
              </p>
            </div>

            <div className="flex gap-2 justify-end mt-2">
              <button 
                onClick={() => setShowScheduleModal(false)}
                className="px-4 py-2 border border-slate-700 hover:bg-slate-800 rounded text-xs font-semibold text-slate-300"
              >
                Cancel
              </button>
              <button 
                onClick={confirmSchedule}
                disabled={!scheduleTime}
                className="px-4 py-2 bg-amber-600 hover:bg-amber-500 disabled:bg-slate-800 text-white rounded text-xs font-semibold transition-colors"
              >
                Confirm Schedule
              </button>
            </div>

          </div>
        </div>
      )}

    </div>
  );
}
