'use client';

import { useEffect } from 'react';

export default function ErrorHandlerInit() {
  useEffect(() => {
    // This runs only on client side
    if (typeof window === 'undefined') return;

    try {
      // Dynamically import error handler on client side
      import('@/lib/errorHandler').then((module) => {
        const errorHandler = module.default;
        
        if (errorHandler && typeof errorHandler.printSummary === 'function') {
          console.log('[ErrorHandler] Initialized');
          
          // Make error handler available in console
          (window as any).errorHandler = errorHandler;
          
          // Log initial info
          console.log('%c Error Handler Active', 'color: #0ea5e9; font-weight: bold');
          console.log('Use errorHandler.printSummary() to see error statistics');
          console.log('Use errorHandler.getErrors() to view all errors');
        }
      });
    } catch (error) {
      console.error('[ErrorHandler] Failed to initialize:', error);
    }

    return () => {
      // Cleanup if needed
    };
  }, []);

  return null;
}
