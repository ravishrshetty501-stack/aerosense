import React, { useState, useRef, useEffect } from 'react';
import { useAQI } from '../../context/AQIContext';
import { api } from '../../services/api';
import { Bot, Send, User, Sparkles, CheckCircle2, ChevronDown, ChevronUp, Database, Compass, Clock, MapPin } from 'lucide-react';

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  toolCalls?: any[];
  groundingData?: any;
  timestamp: string;
}

export const AIAssistantView: React.FC = () => {
  const { activeCity, standard } = useAQI();
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'welcome',
      role: 'assistant',
      content: `Hello! I am **AeroSense AI**, your global environmental health and air quality intelligence assistant. 

I ground every response in real-time measurements from the **WAQI Global Ground Station Network** and atmospheric forecasts from the **Copernicus / Open-Meteo CAMS Model**.

How can I assist you with **${activeCity.name}** or any other city worldwide?`,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    },
  ]);
  const [inputPrompt, setInputPrompt] = useState('');
  const [loading, setLoading] = useState(false);
  const [expandedGrounding, setExpandedGrounding] = useState<Record<string, boolean>>({});
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const promptSuggestions = [
    `Analyze current air quality in ${activeCity.name}`,
    `Is it safe for outdoor running in ${activeCity.name} today?`,
    `Compare air quality between ${activeCity.name} and London`,
    `What are the dominant pollutants and 24h forecast?`,
  ];

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading]);

  const toggleGrounding = (id: string) => {
    setExpandedGrounding((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const handleSend = async (textToSend?: string) => {
    const text = (textToSend || inputPrompt).trim();
    if (!text || loading) return;

    const userMsg: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: text,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInputPrompt('');
    setLoading(true);

    try {
      const history = messages.slice(-6).map((m) => ({ role: m.role, content: m.content }));
      const response = await api.sendChatMessage(text, activeCity.name, history);

      const botMsg: ChatMessage = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: response.response,
        toolCalls: response.tool_calls,
        groundingData: response.grounding_data,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };

      setMessages((prev) => [...prev, botMsg]);
    } catch (e: any) {
      const errorMsg: ChatMessage = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: `I encountered a communication issue with the reasoning engine: ${e.message || 'Connection timeout'}. Please verify your network status.`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // Helper to format simple markdown elements (bold, tables, lists)
  const renderFormattedContent = (content: string) => {
    const lines = content.split('\n');
    const elements: React.ReactNode[] = [];
    let tableRows: string[][] = [];
    let inTable = false;

    lines.forEach((line, idx) => {
      // Table row detection
      if (line.trim().startsWith('|') && line.trim().endsWith('|')) {
        const cells = line
          .split('|')
          .slice(1, -1)
          .map((c) => c.trim());
        if (cells.some((c) => c.includes('---'))) {
          inTable = true;
          return;
        }
        tableRows.push(cells);
        inTable = true;
        return;
      } else if (inTable) {
        if (tableRows.length > 0) {
          const header = tableRows[0];
          const body = tableRows.slice(1);
          elements.push(
            <div key={`table-${idx}`} className="my-3 overflow-x-auto rounded-lg border border-clima-border dark:border-darkClima-border shadow-sm">
              <table className="w-full text-left text-xs">
                <thead className="bg-clima-subtle dark:bg-darkClima-subtle text-clima-text dark:text-darkClima-text">
                  <tr>
                    {header.map((h, i) => (
                      <th key={i} className="px-3 py-2 font-semibold">
                        {h.replace(/\*\*/g, '')}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-clima-border dark:divide-darkClima-border bg-clima-surface dark:bg-darkClima-surface">
                  {body.map((row, rIdx) => (
                    <tr key={rIdx} className="hover:bg-clima-subtle/50 dark:hover:bg-darkClima-subtle/50">
                      {row.map((cell, cIdx) => (
                        <td key={cIdx} className="px-3 py-2 font-mono text-[11px] text-clima-text dark:text-darkClima-text">
                          {cell.replace(/\*\*/g, '')}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          );
          tableRows = [];
        }
        inTable = false;
      }

      // Headers
      if (line.startsWith('### ')) {
        elements.push(
          <h4 key={idx} className="text-sm font-bold text-clima-text dark:text-darkClima-text mt-3 mb-1 font-sans">
            {line.replace('### ', '')}
          </h4>
        );
        return;
      }
      if (line.startsWith('## ')) {
        elements.push(
          <h3 key={idx} className="text-base font-bold text-clima-accent dark:text-darkClima-accent mt-3 mb-1.5 font-sans">
            {line.replace('## ', '')}
          </h3>
        );
        return;
      }

      // Bullet points
      if (line.trim().startsWith('* ') || line.trim().startsWith('- ')) {
        const bulletText = line.trim().substring(2);
        elements.push(
          <div key={idx} className="flex items-start space-x-2 my-1 text-xs text-clima-text dark:text-darkClima-text font-sans">
            <span className="text-clima-accent dark:text-darkClima-accent mt-0.5">•</span>
            <span>
              {bulletText.split(/(\*\*.*?\*\*)/g).map((part, pIdx) => {
                if (part.startsWith('**') && part.endsWith('**')) {
                  return (
                    <strong key={pIdx} className="font-semibold text-clima-accent dark:text-darkClima-accent">
                      {part.slice(2, -2)}
                    </strong>
                  );
                }
                return part;
              })}
            </span>
          </div>
        );
        return;
      }

      // Blank line
      if (!line.trim()) {
        elements.push(<div key={idx} className="h-1.5" />);
        return;
      }

      // Regular paragraph
      elements.push(
        <p key={idx} className="text-xs text-clima-text dark:text-darkClima-text leading-relaxed font-sans">
          {line.split(/(\*\*.*?\*\*)/g).map((part, pIdx) => {
            if (part.startsWith('**') && part.endsWith('**')) {
              return (
                <strong key={pIdx} className="font-semibold text-clima-accent dark:text-darkClima-accent">
                  {part.slice(2, -2)}
                </strong>
              );
            }
            return part;
          })}
        </p>
      );
    });

    return elements;
  };

  return (
    <div className="flex h-[calc(100vh-8.5rem)] max-w-6xl mx-auto border border-clima-border dark:border-darkClima-border rounded-xl bg-clima-surface dark:bg-darkClima-surface overflow-hidden shadow-floating dark:shadow-floating-dark font-sans">
      {/* Left Sidebar: Context & Inquiry Options */}
      <div className="w-64 border-r border-clima-border dark:border-darkClima-border bg-clima-subtle/40 dark:bg-darkClima-subtle/40 p-4 space-y-4 hidden lg:flex flex-col justify-between shrink-0">
        <div className="space-y-4">
          <div>
            <div className="text-[10px] font-semibold uppercase tracking-wider text-clima-muted dark:text-darkClima-muted">
              Spatial Focus
            </div>
            <div className="mt-1 flex items-center space-x-2 bg-clima-surface dark:bg-darkClima-surface p-2.5 rounded-lg border border-clima-border dark:border-darkClima-border">
              <MapPin className="w-4 h-4 text-clima-accent dark:text-darkClima-accent" />
              <div>
                <div className="text-xs font-bold text-clima-text dark:text-darkClima-text">{activeCity.name}</div>
                <div className="text-[10px] text-clima-muted dark:text-darkClima-muted font-mono">
                  {activeCity.latitude.toFixed(2)}°N, {activeCity.longitude.toFixed(2)}°E
                </div>
              </div>
            </div>
          </div>

          <div>
            <div className="text-[10px] font-semibold uppercase tracking-wider text-clima-muted dark:text-darkClima-muted mb-2">
              Suggested Scientific Inquiries
            </div>
            <div className="space-y-1.5">
              {promptSuggestions.map((s, i) => (
                <button
                  key={i}
                  onClick={() => handleSend(s)}
                  className="w-full text-left text-[11px] p-2 bg-clima-surface dark:bg-darkClima-surface hover:bg-clima-subtle dark:hover:bg-darkClima-subtle text-clima-text dark:text-darkClima-text rounded-lg border border-clima-border dark:border-darkClima-border transition-colors leading-tight"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="p-2.5 bg-clima-surface dark:bg-darkClima-surface rounded-lg border border-clima-border dark:border-darkClima-border text-[10px] font-mono text-clima-muted dark:text-darkClima-muted">
          <div>Provider: Google Gemini 1.5 Flash</div>
          <div>Tools: 8 Grounded Handlers</div>
        </div>
      </div>

      {/* Main Chat Workspace */}
      <div className="flex-1 flex flex-col justify-between overflow-hidden">
        {/* Header */}
        <div className="px-5 py-3 border-b border-clima-border dark:border-darkClima-border bg-clima-subtle/50 dark:bg-darkClima-subtle/50 flex items-center justify-between">
          <div className="flex items-center space-x-2.5">
            <div className="w-7 h-7 rounded-lg bg-clima-accent/10 dark:bg-darkClima-accent/10 border border-clima-accent/30 dark:border-darkClima-accent/30 flex items-center justify-center">
              <Bot className="w-4 h-4 text-clima-accent dark:text-darkClima-accent" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h3 className="text-sm font-bold text-clima-text dark:text-darkClima-text font-sans">
                  AeroSense Environmental Intelligence Assistant
                </h3>
                <span className="text-[10px] font-mono px-2 py-0.5 bg-[#23966B]/15 text-[#0f6848] dark:text-[#4BBF87] border border-[#23966B]/30 rounded-full font-medium">
                  Grounded Engine
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Message Feed */}
        <div className="flex-1 overflow-y-auto p-5 space-y-4">
          {messages.map((msg) => {
            const isUser = msg.role === 'user';
            return (
              <div
                key={msg.id}
                className={`flex items-start space-x-3 ${isUser ? 'flex-row-reverse space-x-reverse' : ''}`}
              >
                {/* Avatar */}
                <div
                  className={`w-7 h-7 rounded-lg flex items-center justify-center shrink-0 mt-0.5 ${
                    isUser
                      ? 'bg-clima-accent dark:bg-darkClima-accent text-white dark:text-darkClima-bg'
                      : 'bg-clima-subtle dark:bg-darkClima-subtle text-clima-accent dark:text-darkClima-accent border border-clima-border dark:border-darkClima-border'
                  }`}
                >
                  {isUser ? <User className="w-3.5 h-3.5" /> : <Bot className="w-3.5 h-3.5" />}
                </div>

                {/* Message Bubble */}
                <div className="max-w-[85%] sm:max-w-[78%] space-y-2">
                  <div
                    className={`p-4 rounded-xl shadow-sm ${
                      isUser
                        ? 'bg-clima-accent dark:bg-darkClima-accent text-white dark:text-darkClima-bg font-sans text-xs'
                        : 'bg-clima-subtle/80 dark:bg-darkClima-subtle/80 border border-clima-border dark:border-darkClima-border text-clima-text dark:text-darkClima-text'
                    }`}
                  >
                    {isUser ? <p className="leading-relaxed">{msg.content}</p> : renderFormattedContent(msg.content)}
                  </div>

                  {/* Grounding & Tool Execution Badge */}
                  {!isUser && msg.toolCalls && msg.toolCalls.length > 0 && (
                    <div className="bg-clima-subtle dark:bg-darkClima-subtle border border-clima-border dark:border-darkClima-border rounded-lg p-2.5 space-y-1.5">
                      <div
                        onClick={() => toggleGrounding(msg.id)}
                        className="flex items-center justify-between text-[11px] font-mono text-clima-accent dark:text-darkClima-accent cursor-pointer hover:opacity-80"
                      >
                        <div className="flex items-center space-x-1.5">
                          <Database className="w-3.5 h-3.5" />
                          <span>
                            Verified Tool Execution: {msg.toolCalls.map((t) => t.name).join(', ')}
                          </span>
                        </div>
                        {expandedGrounding[msg.id] ? (
                          <ChevronUp className="w-3.5 h-3.5" />
                        ) : (
                          <ChevronDown className="w-3.5 h-3.5" />
                        )}
                      </div>

                      {expandedGrounding[msg.id] && msg.groundingData && (
                        <div className="mt-2 pt-2 border-t border-clima-border dark:border-darkClima-border text-[10px] font-mono text-clima-text dark:text-darkClima-text bg-clima-surface dark:bg-darkClima-surface p-2 rounded overflow-x-auto max-h-48">
                          <pre>{JSON.stringify(msg.groundingData, null, 2)}</pre>
                        </div>
                      )}
                    </div>
                  )}

                  <div className={`text-[10px] text-clima-muted dark:text-darkClima-muted font-sans ${isUser ? 'text-right' : 'text-left'}`}>
                    {msg.timestamp}
                  </div>
                </div>
              </div>
            );
          })}

          {loading && (
            <div className="flex items-center space-x-3">
              <div className="w-7 h-7 rounded-lg bg-clima-subtle dark:bg-darkClima-subtle border border-clima-border dark:border-darkClima-border text-clima-accent dark:text-darkClima-accent flex items-center justify-center">
                <Bot className="w-3.5 h-3.5 animate-pulse" />
              </div>
              <div className="p-3 bg-clima-subtle dark:bg-darkClima-subtle border border-clima-border dark:border-darkClima-border rounded-xl flex items-center space-x-2">
                <span className="flex h-2 w-2 relative">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-clima-accent dark:bg-darkClima-accent opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-clima-accent dark:bg-darkClima-accent"></span>
                </span>
                <span className="text-xs text-clima-muted dark:text-darkClima-muted font-sans">
                  Querying verified environmental telemetry & running reasoning models...
                </span>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input Bar */}
        <div className="p-3.5 border-t border-clima-border dark:border-darkClima-border bg-clima-surface dark:bg-darkClima-surface">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSend();
            }}
            className="flex items-end space-x-2"
          >
            <textarea
              ref={textareaRef}
              rows={1}
              value={inputPrompt}
              onChange={(e) => setInputPrompt(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={`Ask about ${activeCity.name} air quality, pollutant risks, activity advisories... (Enter to send)`}
              className="flex-1 bg-clima-subtle dark:bg-darkClima-subtle border border-clima-border dark:border-darkClima-border rounded-lg px-3.5 py-2.5 text-xs text-clima-text dark:text-darkClima-text placeholder-clima-muted dark:placeholder-darkClima-muted focus:outline-none focus:border-clima-accent dark:focus:border-darkClima-accent font-sans resize-none max-h-32"
            />
            <button
              type="submit"
              disabled={!inputPrompt.trim() || loading}
              aria-label="Send message to AI Assistant"
              className="p-2.5 bg-clima-accent dark:bg-darkClima-accent hover:opacity-90 disabled:opacity-40 text-white dark:text-darkClima-bg rounded-lg transition-colors shadow-sm"
            >
              <Send className="w-4 h-4" />
            </button>
          </form>
        </div>
      </div>
    </div>
  );
};
