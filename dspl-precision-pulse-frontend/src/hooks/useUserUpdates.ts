import { useEffect, useCallback } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import io, { Socket } from 'socket.io-client';

let socket: Socket | null = null;

export function useUserUpdates() {
  const queryClient = useQueryClient();

  useEffect(() => {
    // Initialize Socket.IO connection
    if (!socket) {
      socket = io('http://localhost:5000', {
        reconnection: true,
        reconnectionDelay: 1000,
        reconnectionDelayMax: 5000,
        reconnectionAttempts: 5,
      });
    }

    // Listen for user creation
    socket.on('user_created', (data) => {
      console.log('[SOCKET] User created:', data);
      queryClient.invalidateQueries({ queryKey: ['users'] });
    });

    // Listen for user updates
    socket.on('user_updated', (data) => {
      console.log('[SOCKET] User updated:', data);
      queryClient.invalidateQueries({ queryKey: ['users'] });
      if (data.user?.id) {
        queryClient.invalidateQueries({ queryKey: ['user', data.user.id] });
      }
    });

    // Listen for user deletion
    socket.on('user_deleted', (data) => {
      console.log('[SOCKET] User deleted:', data);
      queryClient.invalidateQueries({ queryKey: ['users'] });
    });

    // Listen for parameter stream updates
    socket.on('parameter_stream_update', (data) => {
      console.log('[SOCKET] Parameter stream update:', data);
      queryClient.invalidateQueries({ queryKey: ['parameter_stream'] });
    });

    // Listen for parameter value updates
    socket.on('parameter_value_updated', (data) => {
      console.log('[SOCKET] Parameter value updated:', data);
      queryClient.invalidateQueries({ queryKey: ['parameter_stream'] });
      queryClient.invalidateQueries({ queryKey: ['parameters'] });
    });

    return () => {
      // Cleanup on unmount
      if (socket) {
        socket.off('user_created');
        socket.off('user_updated');
        socket.off('user_deleted');
        socket.off('parameter_stream_update');
        socket.off('parameter_value_updated');
      }
    };
  }, [queryClient]);

  return socket;
}

export function disconnectSocket() {
  if (socket) {
    socket.disconnect();
    socket = null;
  }
}
