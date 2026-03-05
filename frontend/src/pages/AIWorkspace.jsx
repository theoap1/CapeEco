import { useState, useRef, useCallback, useEffect } from 'react';
import { Send, Loader2, Building2, Sparkles, RotateCcw, MapPin, X } from 'lucide-react';
import { streamChat, getConversations, createConversation, getConversation, updateConversationTitle, deleteConversation, saveConversationMessages, getProperty } from '../utils/api';
import ChatMessage from '../components/ai/ChatMessage';
import ContextPanel from '../components/ai/ContextPanel';
import SuggestedPrompts from '../components/ai/SuggestedPrompts';
import ConversationSidebar from '../components/ai/ConversationSidebar';

function PropertyPrompts({ property, onSelect }) {
  const label = property.full_address || `ERF ${property.erf_number}, ${property.suburb}`;
  const prompts = [
    { icon: '🔍', text: `Give me a full development analysis of this property`, display: `Give me a full development analysis of ${label}` },
    { icon: '🌿', text: `What are the biodiversity constraints on this property?`, display: `What are the biodiversity constraints on ${label}?` },
    { icon: '☀️', text: `What's the solar and net-zero potential of this property?`, display: `What's the solar and net-zero potential of ${label}?` },
    { icon: '🏗️', text: `What can I build on this property? Show me unit mix and financials.`, display: `What can I build on ${label}? Show me unit mix and financials.` },
  ];
  return (
    <div className="grid grid-cols-2 gap-2 max-w-lg w-full">
      {prompts.map((p, i) => (
        <button
          key={i}
          onClick={() => onSelect(p.text)}
          className="text-left px-3 py-2.5 rounded-lg border border-gray-800 bg-gray-900/50
                     hover:border-ocean-500/30 hover:bg-gray-800/50 transition-all group"
        >
          <span className="text-sm mr-1.5">{p.icon}</span>
          <span className="text-xs text-gray-400 group-hover:text-gray-200 leading-relaxed">{p.display || p.text}</span>
        </button>
      ))}
    </div>
  );
}

export default function AIWorkspace({ selectedPropertyId, onClearProperty }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [contextData, setContextData] = useState(null);
  const [activeContextTab, setActiveContextTab] = useState('property');
  const [panelWidth, setPanelWidth] = useState(() => {
    const saved = localStorage.getItem('siteline-panel-width');
    return saved ? Number(saved) : 420;
  });

  // Conversation persistence
  const [conversations, setConversations] = useState([]);
  const [activeConversationId, setActiveConversationId] = useState(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => {
    return localStorage.getItem('siteline-sidebar-collapsed') === 'true';
  });
  const conversationIdRef = useRef(null); // Tracks active ID inside async flows

  // Linked property from map/search
  const [linkedProperty, setLinkedProperty] = useState(null);
  const loadedPropertyIdRef = useRef(null);

  const chatEndRef = useRef(null);
  const inputRef = useRef(null);

  const handlePanelWidthChange = useCallback((w) => {
    setPanelWidth(w);
    localStorage.setItem('siteline-panel-width', String(w));
  }, []);

  const scrollToBottom = useCallback(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  // Load conversations on mount
  useEffect(() => {
    getConversations().then(data => setConversations(data.conversations || [])).catch(() => {});
  }, []);

  // Fetch linked property when selectedPropertyId changes
  useEffect(() => {
    if (!selectedPropertyId || selectedPropertyId === loadedPropertyIdRef.current) return;
    loadedPropertyIdRef.current = selectedPropertyId;
    getProperty(selectedPropertyId).then(prop => {
      setLinkedProperty(prop);
      // Pre-populate context panel with the property
      setContextData(prev => {
        const merged = prev ? { ...prev } : {};
        merged.property = prop;
        return merged;
      });
      setActiveContextTab('property');
    }).catch(() => {});
  }, [selectedPropertyId]);

  // Keep ref in sync
  useEffect(() => {
    conversationIdRef.current = activeConversationId;
  }, [activeConversationId]);

  const toggleSidebar = useCallback(() => {
    setSidebarCollapsed(prev => {
      localStorage.setItem('siteline-sidebar-collapsed', String(!prev));
      return !prev;
    });
  }, []);

  const handleSend = useCallback(async (text = null) => {
    const messageText = text || input.trim();
    if (!messageText || isStreaming) return;

    const userMessage = { role: 'user', content: messageText };
    const newMessages = [...messages, userMessage];
    setMessages(newMessages);
    setInput('');
    setIsStreaming(true);

    // Create conversation on first message if none active
    let convId = conversationIdRef.current;
    if (!convId) {
      try {
        const titlePreview = messageText.slice(0, 100);
        const conv = await createConversation(titlePreview);
        convId = conv.id;
        setActiveConversationId(convId);
        conversationIdRef.current = convId;
        setConversations(prev => [conv, ...prev]);
      } catch (err) {
        console.warn('Failed to create conversation:', err);
      }
    }

    // Add placeholder for assistant response
    const assistantMessage = { role: 'assistant', content: '', toolCalls: [], isStreaming: true };
    setMessages(prev => [...prev, assistantMessage]);

    try {
      const chatHistory = newMessages.map(m => ({ role: m.role, content: m.content }));
      let fullContent = '';
      let toolCalls = [];

      for await (const event of streamChat(chatHistory, linkedProperty?.id || null)) {
        if (event.type === 'text') {
          fullContent += event.content;
          setMessages(prev => {
            const updated = [...prev];
            updated[updated.length - 1] = {
              ...updated[updated.length - 1],
              content: fullContent,
            };
            return updated;
          });
        } else if (event.type === 'tool_call') {
          toolCalls.push({ name: event.name, status: 'running' });
          setMessages(prev => {
            const updated = [...prev];
            updated[updated.length - 1] = {
              ...updated[updated.length - 1],
              toolCalls: [...toolCalls],
            };
            return updated;
          });
        } else if (event.type === 'tool_result') {
          toolCalls = toolCalls.map(tc =>
            tc.name === event.name ? { ...tc, status: 'done', result: event.result } : tc
          );
          setMessages(prev => {
            const updated = [...prev];
            updated[updated.length - 1] = {
              ...updated[updated.length - 1],
              toolCalls: [...toolCalls],
            };
            return updated;
          });
        } else if (event.type === 'context') {
          setContextData(prev => {
            if (!prev) return event.data;
            const merged = { ...prev };
            if (event.data.property) merged.property = event.data.property;
            if (event.data.biodiversity) merged.biodiversity = event.data.biodiversity;
            if (event.data.constraintMap) merged.constraintMap = event.data.constraintMap;
            if (event.data.analysis) {
              merged.analysis = { ...(prev.analysis || {}), ...event.data.analysis };
            }
            return merged;
          });
          if (event.data.property) setActiveContextTab('property');
          if (event.data.constraintMap) setActiveContextTab('map');
          if (event.data.analysis) setActiveContextTab('data');
        }
      }

      // Mark streaming done
      setMessages(prev => {
        const updated = [...prev];
        updated[updated.length - 1] = {
          ...updated[updated.length - 1],
          content: fullContent,
          isStreaming: false,
        };
        return updated;
      });

      // Save messages to DB (fire-and-forget)
      if (convId) {
        const toSave = [
          { role: 'user', content: messageText },
          { role: 'assistant', content: fullContent, tool_calls: toolCalls.length ? toolCalls : null },
        ];
        saveConversationMessages(convId, toSave).catch(err => console.warn('Save failed:', err));
        // Bump conversation to top of sidebar
        setConversations(prev => {
          const updated = prev.map(c => c.id === convId ? { ...c, updated_at: new Date().toISOString() } : c);
          return updated.sort((a, b) => new Date(b.updated_at) - new Date(a.updated_at));
        });
      }
    } catch (err) {
      setMessages(prev => {
        const updated = [...prev];
        updated[updated.length - 1] = {
          role: 'assistant',
          content: `Sorry, I encountered an error: ${err.message}. Please try again.`,
          isStreaming: false,
          isError: true,
        };
        return updated;
      });
    } finally {
      setIsStreaming(false);
    }
  }, [input, messages, isStreaming]);

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleNewChat = useCallback(() => {
    setMessages([]);
    setContextData(null);
    setInput('');
    setActiveConversationId(null);
    conversationIdRef.current = null;
  }, []);

  const handleSelectConversation = useCallback(async (id) => {
    if (id === activeConversationId || isStreaming) return;
    try {
      const data = await getConversation(id);
      setActiveConversationId(id);
      conversationIdRef.current = id;
      // Restore messages with toolCalls from stored tool_calls field
      const restoredMessages = (data.messages || []).map(m => ({
        role: m.role,
        content: m.content,
        toolCalls: m.tool_calls || undefined,
      }));
      setMessages(restoredMessages);
      setContextData(null);
      setInput('');
    } catch (err) {
      console.warn('Failed to load conversation:', err);
    }
  }, [activeConversationId, isStreaming]);

  const handleDeleteConversation = useCallback(async (id) => {
    try {
      await deleteConversation(id);
      setConversations(prev => prev.filter(c => c.id !== id));
      if (id === activeConversationId) {
        handleNewChat();
      }
    } catch (err) {
      console.warn('Failed to delete conversation:', err);
    }
  }, [activeConversationId, handleNewChat]);

  const handleRenameConversation = useCallback(async (id, newTitle) => {
    try {
      await updateConversationTitle(id, newTitle);
      setConversations(prev => prev.map(c => c.id === id ? { ...c, title: newTitle } : c));
    } catch (err) {
      console.warn('Failed to rename conversation:', err);
    }
  }, []);

  const hasMessages = messages.length > 0;

  return (
    <div className="h-full flex bg-gray-950">
      {/* Conversation sidebar */}
      <ConversationSidebar
        conversations={conversations}
        activeId={activeConversationId}
        onSelect={handleSelectConversation}
        onNewChat={handleNewChat}
        onDelete={handleDeleteConversation}
        onRename={handleRenameConversation}
        collapsed={sidebarCollapsed}
        onToggle={toggleSidebar}
      />

      {/* Chat panel */}
      <div className="flex-1 flex flex-col min-w-0 border-r border-gray-800">
        {/* Chat header */}
        <div className="h-10 border-b border-gray-800 flex items-center px-4 shrink-0">
          <Sparkles className="w-3.5 h-3.5 text-ocean-400 mr-2" />
          <span className="text-xs font-medium text-gray-300">AI Assistant</span>
          {hasMessages && (
            <button
              onClick={handleNewChat}
              className="ml-auto flex items-center gap-1 text-xs text-gray-500 hover:text-gray-300 transition-colors"
            >
              <RotateCcw className="w-3 h-3" />
              New chat
            </button>
          )}
        </div>

        {/* Messages area */}
        <div className="flex-1 overflow-y-auto">
          {!hasMessages ? (
            <div className="h-full flex flex-col items-center justify-center px-6">
              <div className="w-16 h-16 rounded-2xl bg-ocean-600/10 border border-ocean-500/20 flex items-center justify-center mb-5 shadow-lg shadow-ocean-500/10">
                <Building2 className="w-7 h-7 text-ocean-400" />
              </div>
              <h2 className="text-lg font-semibold text-white mb-2">Siteline AI</h2>
              <p className="text-sm text-gray-500 text-center max-w-md mb-4">
                Ask me about any property in Cape Town. I can analyze biodiversity risk,
                zoning constraints, solar potential, crime stats, and more.
              </p>

              {linkedProperty && (
                <div className="flex items-center gap-2 px-3 py-2 mb-6 rounded-lg bg-ocean-600/10 border border-ocean-500/20 max-w-md w-full">
                  <MapPin className="w-3.5 h-3.5 text-ocean-400 shrink-0" />
                  <span className="text-xs text-ocean-300 truncate flex-1">
                    {linkedProperty.full_address || `ERF ${linkedProperty.erf_number}, ${linkedProperty.suburb}`}
                  </span>
                  <button
                    onClick={() => { setLinkedProperty(null); loadedPropertyIdRef.current = null; onClearProperty?.(); }}
                    className="text-gray-500 hover:text-gray-300 shrink-0"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </div>
              )}

              {linkedProperty ? (
                <PropertyPrompts
                  property={linkedProperty}
                  onSelect={(prompt) => handleSend(prompt)}
                />
              ) : (
                <SuggestedPrompts onSelect={(prompt) => handleSend(prompt)} />
              )}
            </div>
          ) : (
            <div className="px-4 py-4 space-y-4">
              {messages.map((msg, i) => (
                <ChatMessage key={i} message={msg} />
              ))}
              <div ref={chatEndRef} />
            </div>
          )}
        </div>

        {/* Input area */}
        <div className="border-t border-gray-800 p-3">
          {linkedProperty && hasMessages && (
            <div className="flex items-center gap-2 px-2 pb-2">
              <MapPin className="w-3 h-3 text-ocean-400 shrink-0" />
              <span className="text-[11px] text-ocean-300/70 truncate">
                {linkedProperty.full_address || `ERF ${linkedProperty.erf_number}, ${linkedProperty.suburb}`}
              </span>
              <button
                onClick={() => { setLinkedProperty(null); loadedPropertyIdRef.current = null; onClearProperty?.(); }}
                className="text-gray-600 hover:text-gray-400 shrink-0"
              >
                <X className="w-3 h-3" />
              </button>
            </div>
          )}
          <div className="flex items-end gap-2 bg-gray-900/80 backdrop-blur-sm border border-gray-700/50 rounded-xl px-3 py-2
                          focus-within:border-ocean-500/50 focus-within:shadow-lg focus-within:shadow-ocean-500/5 transition-all">
            <textarea
              ref={inputRef}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={linkedProperty
                ? `Ask about ${linkedProperty.full_address || `ERF ${linkedProperty.erf_number}`}...`
                : "Ask about a property... (e.g. 'Analyze ERF 901 Bantry Bay')"
              }
              rows={1}
              className="flex-1 bg-transparent text-sm text-gray-100 placeholder-gray-500 resize-none
                         focus:outline-none min-h-[36px] max-h-[120px]"
              style={{ height: 'auto' }}
              onInput={e => {
                e.target.style.height = 'auto';
                e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px';
              }}
            />
            <button
              onClick={() => handleSend()}
              disabled={!input.trim() || isStreaming}
              className="w-8 h-8 rounded-lg bg-ocean-600 hover:bg-ocean-500 disabled:bg-gray-700 disabled:text-gray-500
                         text-white flex items-center justify-center transition-colors shrink-0"
            >
              {isStreaming ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Send className="w-4 h-4" />
              )}
            </button>
          </div>
          <p className="text-[10px] text-gray-600 mt-1.5 px-1">
            AI can search properties, run analyses, and pull data from Siteline's database.
          </p>
        </div>
      </div>

      {/* Context panel */}
      <ContextPanel
        data={contextData}
        activeTab={activeContextTab}
        onTabChange={setActiveContextTab}
        width={panelWidth}
        onWidthChange={handlePanelWidthChange}
      />
    </div>
  );
}
