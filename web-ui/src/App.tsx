import React, { useState, useEffect } from 'react';
import '@cloudscape-design/global-styles/index.css';
import { BreadcrumbGroup, Alert, Container, Box, Button } from '@cloudscape-design/components';

// Context Providers
import { AgentRegistryProvider } from './contexts/AgentRegistryContext';

// Components and Pages
import Layout from './components/Layout';
import AgentsPage from './pages/AgentsPage';
import RegisterPage from './pages/RegisterPage';
import { ProtectedRoute } from './components/ProtectedRoute';
import { router } from './utils/router';

// Error Boundary for authentication errors
class AuthErrorBoundary extends React.Component<
  { children: React.ReactNode },
  { hasError: boolean; error?: Error }
> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('Authentication error:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <Container>
          <Box textAlign="center" padding="xxl">
            <Alert
              type="error"
              header="Authentication Error"
              action={
                <Button onClick={() => window.location.reload()}>
                  Reload Page
                </Button>
              }
            >
              There was an error with authentication. Please try reloading the page.
              {this.state.error && (
                <Box variant="small" color="text-status-error" padding={{ top: 's' }}>
                  {this.state.error.message}
                </Box>
              )}
            </Alert>
          </Box>
        </Container>
      );
    }

    return this.props.children;
  }
}

function App() {
  const [currentPath, setCurrentPath] = useState(router.getCurrentPath());

  useEffect(() => {
    const unsubscribe = router.subscribe(setCurrentPath);
    return unsubscribe;
  }, []);

  const renderContent = () => {
    switch (currentPath) {
      case '/register':
        return <RegisterPage />;
      case '/agents':
      case '/':
      default:
        return <AgentsPage />;
    }
  };

  const getBreadcrumbs = () => {
    const breadcrumbItems = [
      { text: 'Agent Registry', href: '/' },
    ];

    switch (currentPath) {
      case '/register':
        breadcrumbItems.push({ text: 'Register Agent', href: '/register' });
        break;
      case '/agents':
      case '/':
      default:
        breadcrumbItems.push({ text: 'Agents', href: '/agents' });
        break;
    }

    return (
      <BreadcrumbGroup
        items={breadcrumbItems}
        onFollow={(event) => {
          event.preventDefault();
          if (event.detail.href) {
            router.navigate(event.detail.href);
          }
        }}
      />
    );
  };

  return (
    <AuthErrorBoundary>
      <ProtectedRoute>
        <AgentRegistryProvider>
          <Layout
            breadcrumbs={getBreadcrumbs()}
            activeHref={currentPath}
          >
            {renderContent()}
          </Layout>
        </AgentRegistryProvider>
      </ProtectedRoute>
    </AuthErrorBoundary>
  );
}

export default App;