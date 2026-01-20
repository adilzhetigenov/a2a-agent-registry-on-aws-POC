// Navigation component for AWS Console-like layout
import React from 'react';
import { SideNavigation, SideNavigationProps } from '@cloudscape-design/components';
import { router } from '../utils/router';

interface NavigationProps {
  activeHref?: string;
  onFollow?: SideNavigationProps['onFollow'];
}

const Navigation: React.FC<NavigationProps> = ({ activeHref = '/agents', onFollow }) => {
  const navigationItems = [
    {
      type: 'section' as const,
      text: 'Agent Registry',
      items: [
        {
          type: 'link' as const,
          text: 'Agents',
          href: '/agents',
        },
        {
          type: 'link' as const,
          text: 'Register Agent',
          href: '/register',
        },
      ],
    },
  ];

  const handleFollow = (event: Parameters<NonNullable<SideNavigationProps['onFollow']>>[0]) => {
    event.preventDefault();
    if (event.detail.href) {
      router.navigate(event.detail.href);
    }
    if (onFollow) {
      onFollow(event);
    }
  };

  return (
    <SideNavigation
      activeHref={activeHref}
      header={{
        href: '/',
        text: 'Agent Registry',
      }}
      items={navigationItems}
      onFollow={handleFollow}
    />
  );
};

export default Navigation;