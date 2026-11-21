import React, { useState, useRef, useEffect } from 'react';
import { useAQI } from '../../context/AQIContext';
import { api } from '../../services/api';
import { Bot, Send, User, Sparkles, Terminal, CheckCircle2, AlertCircle } from 'lucide-react';

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  toolCalls?: any[];
  groundingData?: any;
  timestamp: string;
}

export const AIAssistantView: React.FC = () => {
  const { activeCity } = useAQI();
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'welcome',
      role: 'assistant',
      content: `Hello! I am **AeroSense AI**, your verified global air quality intelligence assistant. I ground my reasoning directly in live sensor observations from **OpenAQ API v3** and **Open-Meteo CAMS models**.\n\nYou can ask me about current pollution levels, city comparisons, outdoor activity safety, or 48-hour atmospheric forecasts.`,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    },
  ]);
  const [inputPrompt, setInputPrompt] = useState('');
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const promptSuggestions = [
    `Analyze current air quality in ${activeCity.name}`,
    `Is today safe for outdoor running in ${activeCity.name}?`,
    `Compare air quality between ${activeCity.name} and London`,
    `What are the dominant pollutants and forecast risk for tomorrow?`,
  ];

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSend = async (textToSend?: string) => {
    const text = textToSend || inputPrompt;
    if (!text.trim() || loading) return;

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
      const history = messages.map((m) => ({ role: m.role, content: m.content }));
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
        content: `Error executing AI reasoning: ${e.message || 'Network timeout'}. Please verify backend connection.`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-8.5rem)] max-w-5xl mx-auto border border-surface-border rounded-lg bg-navy-950/90 overflow-hidden shadow-2xl">
      {/* Header */}
      <div className="px-5 py-3.5 border-b border-surface-border bg-navy-900 flex items-center justify-between">
        <div className="flex items-center space-x-2.5">
          <div className="w-7 h-7 rounded-md bg-cyanAccent/15 border border-cyanAccent/30 flex items-center justify-center">
            <Bot className="w-4 h-4 text-cyanAccent" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-white font-mono flex items-center space-x-2">
              <span>GENAI ENVIRONMENTAL INTELLIGENCE ASSISTANT</span>
              <span className="text-[10px] font-mono px-2 py-0.2 bg-emerald-950 text-emerald-400 border border-emerald-800 rounded">
                GROUNDED REASONING
              </span>
            </h3>
            <p className="text-[11px] text-slate-400 font-mono">
              Controlled Function Calling Engine • Context Location: {activeCity.name}
            </p>
          </div>
        </div>
      </div>

      {/* Messages Scroll Area */}
      <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-4">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex items-start space-x-3 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            {msg.role === 'assistant' && (
              <div className="w-7 h-7 rounded bg-navy-850 border border-slate-700 flex items-center justify-center shrink-0 mt-1">
                <Bot className="w-4 h-4 text-cyanAccent" />
              </div>
            )}

            <div
              className={`max-w-2xl rounded-lg p-4 text-xs sm:text-sm leading-relaxed ${
                msg.role === 'user'
                  ? 'bg-cyanAccent/15 border border-cyanAccent/30 text-cyan-50'
                  : 'bg-navy-900 border border-slate-800 text-slate-200'
              }`}
            >
              {/* Tool Execution Transparency Badge */}
              {msg.toolCalls && msg.toolCalls.length > 0 && (
                <div className="mb-3 p-2 bg-navy-950 border border-slate-800 rounded font-mono text-[11px] space-y-1">
                  <div className="flex items-center text-cyanAccent">
                    <Terminal className="w-3.5 h-3.5 mr-1" />
                    <span>Backend Tool Executed:</span>
                  </div>
                  {msg.toolCalls.map((tc, idx) => (
                    <div key={idx} className="text-slate-400 pl-4">
                      <code>{tc.name}({JSON.stringify(tc.args)})</code>
                    </div>
                  ))}
                </div>
              )}

              {/* Message Content */}
              <div className="prose prose-invert max-w-none text-xs sm:text-sm space-y-2 whitespace-pre-line font-sans">
                {msg.content}
              </div>

              <div className="mt-2 text-[10px] font-mono text-slate-500 text-right">
                {msg.timestamp}
              </div>
            </div>

            {msg.role === 'user' && (
              <div className="w-7 h-7 rounded bg-cyanAccent/20 border border-cyanAccent/40 flex items-center justify-center shrink-0 mt-1">
                <User className="w-4 h-4 text-cyanAccent" />
              </div>
            )}
          </div>
        ))}

        {loading && (
          <div className="flex items-start space-x-3">
            <div className="w-7 h-7 rounded bg-navy-850 border border-slate-700 flex items-center justify-center shrink-0">
              <Bot className="w-4 h-4 text-cyanAccent animate-pulse" />
            </div>
            <div className="bg-navy-900 border border-slate-800 rounded-lg p-3 text-xs font-mono text-cyanAccent flex items-center space-x-2">
              <Sparkles className="w-3.5 h-3.5 animate-spin" />
              <span>Querying verified environmental APIs and synthesizing grounded intelligence...</span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Suggested Prompts */}
      <div className="p-3 bg-navy-900/50 border-t border-slate-800/80">
        <div className="flex items-center space-x-2 overflow-x-auto pb-1 scrollbar-none">
          <span className="text-[10px] font-mono uppercase tracking-wider text-slate-500 shrink-0">
            Suggested Queries:
          </span>
          {promptSuggestions.map((prompt, idx) => (
            <button
              key={idx}
              onClick={() => handleSend(prompt)}
              className="px-2.5 py-1 bg-navy-950 hover:bg-navy-850 border border-slate-800 text-[11px] text-slate-300 rounded font-mono shrink-0 transition-colors"
            >
              {prompt}
            </button>
          ))}
        </div>
      </div>

      {/* Input Form */}
      <div className="p-4 bg-navy-900 border-t border-surface-border">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSend();
          }}
          className="flex items-center space-x-2"
        >
          <input
            type="text"
            placeholder="Ask AeroSense AI about current AQI, health precautions, forecasts..."
            value={inputPrompt}
            onChange={(e) => setInputPrompt(e.target.value)}
            disabled={loading}
            className="flex-1 bg-navy-950 border border-slate-700/80 rounded-md px-3.5 py-2 text-xs sm:text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyanAccent transition-colors"
          />
          <button
            type="submit"
            disabled={loading || !inputPrompt.trim()}
            className="px-4 py-2 bg-cyanAccent text-navy-950 font-semibold text-xs sm:text-sm rounded-md hover:bg-cyan-300 disabled:opacity-50 transition-colors flex items-center space-x-1.5"
          >
            <span>Analyze</span>
            <Send className="w-3.5 h-3.5" />
          </button>
        </form>
        <div className="mt-2 text-[10px] text-slate-500 text-center font-mono">
          Disclaimer: Environmental risk calculations are based on EPA and CPCB outdoor ambient standards; not intended for individualized medical diagnosis.
        </div>
      </div>
    </div>
  );
};
