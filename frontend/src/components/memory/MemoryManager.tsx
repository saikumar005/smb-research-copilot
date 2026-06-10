import React, { useEffect, useState } from 'react';
import { Trash2, ArrowLeft, RefreshCw, AlertCircle } from 'lucide-react';
import { apiClient } from '../../api/client';
import { Spinner } from '../ui/Spinner';

interface MemoryFact {
  id: string;
  content: string;
}

interface MemoryManagerProps {
  onBackToChat: () => void;
}

export const MemoryManager: React.FC<MemoryManagerProps> = ({ onBackToChat }) => {
  const [memories, setMemories] = useState<MemoryFact[]>([]);
  const [loading, setLoading] = useState(true);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchMemories = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await apiClient.get<MemoryFact[]>('/memory');
      setMemories(res.data);
    } catch (err: any) {
      console.error(err);
      setError('Could not retrieve memory items from the server.');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      setDeletingId(id);
      setError(null);
      await apiClient.delete(`/memory/${id}`);
      setMemories((prev) => prev.filter((m) => m.id !== id));
    } catch (err: any) {
      console.error(err);
      setError('Failed to delete the memory fact. Please try again.');
    } finally {
      setDeletingId(null);
    }
  };

  useEffect(() => {
    fetchMemories();
  }, []);

  return (
    <div className="memory-workspace-container">
      <div className="memory-header-section animate-fade-in">
        <div>
          <h2>Manage Long-Term Memory</h2>
          <p className="memory-description">
            The Business Research Copilot extracts facts and preferences from your conversations to personalize future interactions. View and delete facts below.
          </p>
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button className="glow-btn-base glow-btn-secondary" onClick={fetchMemories} title="Refresh memory facts list">
            <RefreshCw size={16} />
          </button>
          <button className="glow-btn-base glow-btn" onClick={onBackToChat}>
            <ArrowLeft size={16} />
            <span>Back to Chat</span>
          </button>
        </div>
      </div>

      {error && (
        <div className="toast-card toast-error animate-fade-in" style={{ maxWidth: 'none', margin: '0' }}>
          <AlertCircle size={18} />
          <span className="toast-text">{error}</span>
        </div>
      )}

      {loading ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: '60px' }}>
          <Spinner size="lg" />
        </div>
      ) : memories.length === 0 ? (
        <div className="empty-memories-box animate-fade-in">
          <AlertCircle size={36} />
          <h3>No Stored Memories Yet</h3>
          <p>
            As you discuss sales targets, email preferences, and business criteria, facts will automatically appear here.
          </p>
        </div>
      ) : (
        <div className="memories-card-grid animate-fade-in">
          {memories.map((memory) => (
            <div key={memory.id} className="memory-row-card">
              <span className="memory-fact-text">{memory.content}</span>
              <button
                className="delete-memory-btn"
                onClick={() => handleDelete(memory.id)}
                disabled={deletingId === memory.id}
                title="Remove memory fact"
              >
                {deletingId === memory.id ? (
                  <Spinner size="sm" />
                ) : (
                  <Trash2 size={16} />
                )}
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
