import React, { useEffect, useState } from 'react';
import { useAuth } from '../hooks/useAuth';
import { Container, Spinner, Box } from '@cloudscape-design/components';
import { Auth } from 'aws-amplify';

interface ProtectedRouteProps {
  children: React.ReactNode;
}

export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ children }) => {
  const { signInWithHostedUI } = useAuth();
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  useEffect(() => {
    // If not loading and not authenticated, redirect to hosted UI
    Auth.currentAuthenticatedUser().then(() => {
        setIsAuthenticated(true);
    }).catch(() => {
        signInWithHostedUI();
    });
  }, [signInWithHostedUI]);

  if (!isAuthenticated) {
    // Show loading while redirecting to hosted UI
    return (
      <Container>
        <Box textAlign="center" padding="xxl">
          <Spinner size="large" />
          <Box variant="p" padding={{ top: 'm' }}>
            Redirecting to sign in...
          </Box>
        </Box>
      </Container>
    );
  }

  return <>{children}</>;
};