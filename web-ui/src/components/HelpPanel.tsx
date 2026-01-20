// Help panel component for AWS Console-like layout
import React from 'react';
import { HelpPanel as CloudscapeHelpPanel, Link } from '@cloudscape-design/components';

const HelpPanel: React.FC = () => {
  return (
    <CloudscapeHelpPanel
      header={<h2>Agent Registry Help</h2>}
    >
      <div>
        <h3>About Agent Registry</h3>
        <p>
          The Agent Registry Service manages and tracks agent registrations, heartbeats, and discovery.
          Use this interface to view registered agents, monitor their status, and register new agents.
        </p>
        
        <h3>Key Features</h3>
        <ul>
          <li><strong>Agent Discovery:</strong> Search and filter agents by skills, name, and version</li>
          <li><strong>Manual Registration:</strong> Upload agent cards in JSON format to register new agents</li>
          <li><strong>Pagination:</strong> Navigate through large lists of agents efficiently</li>
        </ul>

        <h3>Getting Started</h3>
        <ol>
          <li>Navigate to the <strong>Agents</strong> page to view all registered agents</li>
          <li>Use the search and filter options to find specific agents</li>
          <li>Click <strong>Register Agent</strong> to add new agents to the registry</li>
          <li>Use the <strong>View JSON</strong> button to see agent card details</li>
          <li>Use the <strong>Delete</strong> button to remove agents from the registry</li>
        </ol>

        <h3>Agent Registration</h3>
        <p>
          To register a new agent, you need to provide an AgentCard JSON that includes:
        </p>
        <ul>
          <li><strong>Basic Info:</strong> name, description, version, url</li>
          <li><strong>Protocol:</strong> protocolVersion, preferredTransport</li>
          <li><strong>Skills:</strong> Array of skill objects with id, name, description, and tags</li>
          <li><strong>Capabilities:</strong> Object with streaming and pushNotifications booleans</li>
          <li><strong>Communication:</strong> defaultInputModes and defaultOutputModes arrays</li>
        </ul>

        <h3>Learn More</h3>
        <p>
          For more information about the A2A protocol and agent development, visit the{' '}
          <Link external href="https://github.com/a2a-protocol">
            A2A Protocol Documentation
          </Link>
        </p>
      </div>
    </CloudscapeHelpPanel>
  );
};

export default HelpPanel;