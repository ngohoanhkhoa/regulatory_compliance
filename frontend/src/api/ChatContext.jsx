import { createContext, useContext, useState } from "react";

const ChatContext = createContext(null);

export function ChatProvider({ children }) {
  const [messages, setMessages] = useState([]);
  const [activeConversationId, setActiveConversationId] = useState(null);

  return (
    <ChatContext.Provider
      value={{ messages, setMessages, activeConversationId, setActiveConversationId }}
    >
      {children}
    </ChatContext.Provider>
  );
}

export function useChat() {
  return useContext(ChatContext);
}
