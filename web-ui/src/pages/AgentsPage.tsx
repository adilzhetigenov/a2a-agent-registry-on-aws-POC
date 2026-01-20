// Agents page - main agent registry functionality
import React from 'react';
import {
  ContentLayout,
  Header,
} from '@cloudscape-design/components';
import AgentRegistry from '../components/AgentRegistry';
import { router } from '../utils/router';

const AgentsPage: React.FC = () => {
  const handleRegisterAgent = () => {
    router.navigate('/register');
  };

  return (
    <ContentLayout
      header={
        <Header
          variant="h1"
          description="View and manage registered agents in the system. Search by name, skills, and version."
        >
          Agent Registry
        </Header>
      }
    >
      <AgentRegistry onRegisterAgent={handleRegisterAgent} />
    </ContentLayout>
  );
};

export default AgentsPage;