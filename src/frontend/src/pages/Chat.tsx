import { useState, useRef, useEffect } from 'react';
import { useStore } from '../store';
import { MessageBubble } from '../components/MessageBubble';
import { SourceCard } from '../components/SourceCard';
import { ConfidenceBadge } from '../components/ConfidenceBadge';
import { SettingsPanel } from '../components/SettingsPanel';
import { Send, Bot, User, Settings } from 'lucide-react';
import axios from 'axios';
import { marked } from 'marked';

interface ChatProps {}

export function Chat(_props: ChatProps) {
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [currentSources, setCurrentSources] = useState<any[]>([]);

  const { conversations, currentConversationId, addMessage, newConversation, settings } = useStore();
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [conversations, currentConversationId]);

  const currentConversation = conversations.find((c) => c.id === currentConversationId);
  const messages = currentConversation?.messages || [];

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage = {
      id: crypto.randomUUID(),
      role: 'user' as const,
      content: input.trim(),
    };

    addMessage(userMessage);
    setInput('');
    setIsLoading(true);

    try {
      const response = await axios.post('/api/v1/chat', {
        query: userMessage.content,
        strict: settings.strictMode,
        top_k: settings.topK,
      });

      const assistantMessage = {
        id: crypto.randomUUID(),
        role: 'assistant' as const,
        content: response.data.answer,
        sources: response.data.sources,
        confidence: response.data.confidence,
        gaps: response.data.gaps,
      };

      addMessage(assistantMessage);
      setCurrentSources(response.data.sources);
    } catch (error: any) {
      console.error('Chat error:', error);
      const errorMessage = {
        id: crypto.randomUUID(),
        role: 'assistant' as const,
        content: `Error: ${error.response?.data?.detail || 'Failed to get response'}`,
      };
      addMessage(errorMessage);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex flex-col h-screen max-w-5xl mx-auto">
      {/* Settings Panel Overlay */}
      {showSettings && (
        <div className="absolute right-4 top-16 z-10 bg-white rounded-lg shadow-lg border p-4 w-64">
          <SettingsPanel onClose={() => setShowSettings(false)} />
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-6 space-y-6">
        {messages.length === 0 && (
          <div className="text-center mt-20">
            <Bot className="w-16 h-16 mx-auto text-blue-500 mb-4" />
            <h2 className="text-2xl font-semibold text-gray-800 mb-2">
              Verity Assistant
            </h2>
            <p className="text-gray-600 max-w-md mx-auto">
              I'm a factual AI. Ask me anything verifiable, and I'll answer with sources.
            </p>
          </div>
        )}

        {messages.map((msg) => (
          <div key={msg.id} className="space-y-2">
            <MessageBubble message={msg} />

            {/* Inline sources for assistant messages */}
            {msg.role === 'assistant' && msg.sources && msg.sources.length > 0 && (
              <div className="ml-12 space-y-2">
                {msg.sources.slice(0, 3).map((source, idx) => (
                  <SourceCard key={idx} source={source} />
                ))}
                {msg.sources.length > 3 && (
                  <p className="text-sm text-gray-500">
                    +{msg.sources.length - 3} more sources
                  </p>
                )}
              </div>
            )}
          </div>
        ))}

        {isLoading && (
          <div className="flex items-center space-x-2 text-gray-500">
            <div className="animate-spin w-5 h-5 border-2 border-blue-500 border-t-transparent rounded-full" />
            <span>Verifying facts and generating answer…</span>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="border-t bg-white px-4 py-4">
        <div className="flex space-x-4">
          <button
            onClick={() => setShowSettings(!showSettings)}
            className="p-2 text-gray-500 hover:text-gray-700"
            title="Settings"
          >
            <Settings className="w-5 h-5" />
          </button>
          <div className="flex-1 relative">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask a factual question…"
              rows={1}
              className="w-full resize-none border border-gray-300 rounded-lg px-4 py-3 pr-12 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              disabled={isLoading}
            />
            <button
              onClick={handleSend}
              disabled={isLoading || !input.trim()}
              className="absolute right-2 top-1/2 -translate-y-1/2 p-2 bg-blue-500 text-white rounded hover:bg-blue-600 disabled:opacity-50"
            >
              <Send className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Confidence indicator for latest response */}
        {messages.length > 0 && messages[messages.length - 1].role === 'assistant' && (
          <div className="mt-2 flex items-center justify-end space-x-2">
            <span className="text-xs text-gray-500">Confidence</span>
            <ConfidenceBadge
              confidence={messages[messages.length - 1].confidence || 'Low'}
            />
          </div>
        )}
      </div>
    </div>
  );
}
