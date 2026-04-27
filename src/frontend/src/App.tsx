import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Chat } from './pages/Chat';
import { History } from './pages/History';
import { Admin } from './pages/Admin';

const queryClient = new QueryClient();

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <div className="min-h-screen bg-gray-50">
          <header className="bg-white border-b border-gray-200 px-6 py-4">
            <div className="flex items-center justify-between">
              <h1 className="text-xl font-semibold text-gray-800">
                Verity Assistant
              </h1>
              <nav className="space-x-4">
                <a href="/" className="text-blue-600 hover:underline">Chat</a>
                <a href="/history" className="text-gray-600 hover:underline">History</a>
                <a href="/admin" className="text-gray-600 hover:underline">Admin</a>
              </nav>
            </div>
          </header>

          <main>
            <Routes>
              <Route path="/" element={<Chat />} />
              <Route path="/history" element={<History />} />
              <Route path="/admin" element={<Admin />} />
            </Routes>
          </main>
        </div>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
