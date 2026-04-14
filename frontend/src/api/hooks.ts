import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiFetch, apiDelete } from './client';
import type { SessionInfo, SessionDetail, FileEntry, DiffEntry, ConversationMessage } from './types';

export function useSessions() {
  return useQuery({
    queryKey: ['sessions'],
    queryFn: () => apiFetch<SessionInfo[]>('/sessions'),
    refetchInterval: (query) => {
      const data = query.state.data;
      if (data?.some((s) => s.status === 'running' || s.status === 'pending')) {
        return 5000;
      }
      return false;
    },
  });
}

export function useSession(sessionId: string) {
  return useQuery({
    queryKey: ['session', sessionId],
    queryFn: () => apiFetch<SessionDetail>(`/sessions/${sessionId}`),
    enabled: !!sessionId && sessionId !== 'pending',
    refetchInterval: (query) => {
      const data = query.state.data;
      if (data?.status === 'running' || data?.status === 'pending') {
        return 3000;
      }
      return false;
    },
  });
}

export function useSessionFiles(sessionId: string, path?: string) {
  const url = path
    ? `/sessions/${sessionId}/files/${path}`
    : `/sessions/${sessionId}/files`;
  return useQuery({
    queryKey: ['files', sessionId, path ?? ''],
    queryFn: () => apiFetch<FileEntry[]>(url),
    enabled: !!sessionId && sessionId !== 'pending',
  });
}

export function useSessionDiff(sessionId: string, enabled: boolean) {
  return useQuery({
    queryKey: ['diff', sessionId],
    queryFn: () => apiFetch<DiffEntry[]>(`/sessions/${sessionId}/diff`),
    enabled: enabled && !!sessionId && sessionId !== 'pending',
  });
}

export function useSessionConversation(sessionId: string, enabled: boolean) {
  return useQuery({
    queryKey: ['conversation', sessionId],
    queryFn: () => apiFetch<ConversationMessage[]>(`/sessions/${sessionId}/conversation`),
    enabled: enabled && !!sessionId && sessionId !== 'pending',
  });
}

export function useSessionSummary(sessionId: string, enabled: boolean) {
  return useQuery({
    queryKey: ['summary', sessionId],
    queryFn: () => apiFetch<{ content: string }>(`/sessions/${sessionId}/summary`),
    enabled: enabled && !!sessionId && sessionId !== 'pending',
  });
}

export function useDeleteSession() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (sessionId: string) => apiDelete(`/sessions/${sessionId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sessions'] });
    },
  });
}
