// Main layout component with AWS Console-like interface
import React from 'react';
import {
  AppLayout,
  TopNavigation,
  Flashbar,
  FlashbarProps,
} from '@cloudscape-design/components';
import Navigation from './Navigation';
import HelpPanel from './HelpPanel';
import { useNavigation } from '../hooks/useNavigation';
import { useAuth } from '../hooks/useAuth';

interface LayoutProps {
  children: React.ReactNode;
  notifications?: FlashbarProps.MessageDefinition[];
  breadcrumbs?: React.ReactNode;
  activeHref?: string;
}

const Layout: React.FC<LayoutProps> = ({ 
  children, 
  notifications = [], 
  breadcrumbs,
  activeHref = '/agents'
}) => {
  const { navigationState, handleNavigationChange, toggleNavigation, toggleTools } = useNavigation(activeHref);
  const { user, signOut } = useAuth();

  const handleSignOut = async () => {
    try {
      await signOut();
    } catch (error) {
      console.error('Sign out failed:', error);
    }
  };

  return (
    <>
      <TopNavigation
        identity={{
          href: '/',
          title: 'Agent Registry Service',
        }}
        utilities={[
          {
            type: 'menu-dropdown',
            text: user?.username || 'User',
            description: (user as any)?.attributes?.email || '',
            iconName: 'user-profile',
            items: [
              {
                id: 'signout',
                text: 'Sign out',
              },
            ],
            onItemClick: ({ detail }) => {
              if (detail.id === 'signout') {
                handleSignOut();
              }
            },
          },
          {
            type: 'button',
            text: 'Help',
            onClick: toggleTools,
          },
        ]}
      />
      <AppLayout
        navigation={
          <Navigation
            activeHref={navigationState.activeHref}
            onFollow={handleNavigationChange}
          />
        }
        navigationOpen={navigationState.navigationOpen}
        onNavigationChange={({ detail }) => {
          if (detail.open !== undefined) {
            toggleNavigation();
          }
        }}
        tools={<HelpPanel />}
        toolsOpen={navigationState.toolsOpen}
        onToolsChange={({ detail }) => {
          if (detail.open !== undefined) {
            toggleTools();
          }
        }}
        breadcrumbs={breadcrumbs}
        notifications={
          notifications.length > 0 ? (
            <Flashbar items={notifications} />
          ) : undefined
        }
        content={children}
        contentType="default"
        stickyNotifications
      />
    </>
  );
};

export default Layout;