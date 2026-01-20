// Navigation hook for managing navigation state
import { useState } from 'react';
import { router } from '../utils/router';

interface NavigationState {
  activeHref: string;
  navigationOpen: boolean;
  toolsOpen: boolean;
}

export const useNavigation = (initialActiveHref: string = '/agents') => {
  const [navigationState, setNavigationState] = useState<NavigationState>({
    activeHref: initialActiveHref,
    navigationOpen: true,
    toolsOpen: false,
  });

  const handleNavigationChange = (event: any) => {
    event.preventDefault();
    if (event.detail.href) {
      router.navigate(event.detail.href);
      setNavigationState(prev => ({
        ...prev,
        activeHref: event.detail.href,
      }));
    }
  };

  const toggleNavigation = () => {
    setNavigationState(prev => ({
      ...prev,
      navigationOpen: !prev.navigationOpen,
    }));
  };

  const toggleTools = () => {
    setNavigationState(prev => ({
      ...prev,
      toolsOpen: !prev.toolsOpen,
    }));
  };

  return {
    navigationState,
    handleNavigationChange,
    toggleNavigation,
    toggleTools,
  };
};