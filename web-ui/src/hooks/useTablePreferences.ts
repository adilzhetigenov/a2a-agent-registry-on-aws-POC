// Hook for managing table preferences with localStorage persistence
import { useState, useEffect } from 'react';

interface TablePreferences {
  pageSize: number;
  visibleContent: string[];
  wrapLines: boolean;
  stripedRows: boolean;
  contentDensity: 'comfortable' | 'compact';
}

interface UseTablePreferencesOptions {
  storageKey: string;
  defaultPreferences: TablePreferences;
}

export const useTablePreferences = (options: UseTablePreferencesOptions) => {
  const { storageKey, defaultPreferences } = options;

  const [preferences, setPreferences] = useState<TablePreferences>(() => {
    try {
      const stored = localStorage.getItem(storageKey);
      if (stored) {
        const parsed = JSON.parse(stored);
        return { ...defaultPreferences, ...parsed };
      }
    } catch (error) {
      console.warn('Failed to load table preferences from localStorage:', error);
    }
    return defaultPreferences;
  });

  // Save preferences to localStorage whenever they change
  useEffect(() => {
    try {
      localStorage.setItem(storageKey, JSON.stringify(preferences));
    } catch (error) {
      console.warn('Failed to save table preferences to localStorage:', error);
    }
  }, [preferences, storageKey]);

  const handlePreferencesChange = (detail: any) => {
    setPreferences(detail.preferences);
  };

  return {
    preferences,
    handlePreferencesChange,
  };
};