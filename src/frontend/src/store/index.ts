import { create } from 'zustand';

interface Conversation {
  id: string;
  messages: Message[];
  createdAt: Date;
}

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: Source[];
  confidence?: string;
  gaps?: string[];
}

interface Source {
  id: number;
  title: string;
  url?: string;
}

interface AppState {
  conversations: Conversation[];
  currentConversationId: string | null;
  settings: {
    strictMode: boolean;
    topK: number;
  };
  setConversation: (id: string) => void;
  addMessage: (msg: Message) => void;
  newConversation: () => string;
}

export const useStore = create<AppState>((set) => ({
  conversations: [],
  currentConversationId: null,
  settings: {
    strictMode: false,
    topK: 5,
  },
  setConversation: (id) => set({ currentConversationId: id }),
  addMessage: (msg) =>
    set((state) => {
      if (!state.currentConversationId) return state;
      const convs = state.conversations.map((c) =>
        c.id === state.currentConversationId
          ? { ...c, messages: [...c.messages, msg] }
          : c
      );
      return { conversations: convs };
    }),
  newConversation: () => {
    const id = crypto.randomUUID();
    set((state) => ({
      conversations: [
        ...state.conversations,
        { id, messages: [], createdAt: new Date() },
      ],
      currentConversationId: id,
    }));
    return id;
  },
}));
