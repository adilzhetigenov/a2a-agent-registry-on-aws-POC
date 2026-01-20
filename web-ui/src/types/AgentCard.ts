// TypeScript interfaces matching the A2A Protocol AgentCard structure

export interface AgentProvider {
  organization?: string;
  url?: string;
}

export interface AgentCapabilities {
  extensions?: string[];
  pushNotifications?: boolean;
  stateTransitionHistory?: boolean;
  streaming?: boolean;
}

export interface AgentSkill {
  id: string;
  name: string;
  description?: string;
  examples?: string[];
  inputModes?: string[];
  outputModes?: string[];
  security?: any[];
  tags?: string[];
}

export interface AgentCard {
  name: string;
  description?: string;
  protocolVersion: string;
  url: string;
  version?: string;
  preferredTransport?: string;
  provider?: AgentProvider;
  capabilities?: AgentCapabilities;
  skills?: AgentSkill[] | string[]; // Support both formats: objects (A2A standard) and strings (current server validation)
  iconUrl?: string;
  documentationUrl?: string;
  additionalInterfaces?: any[];
  defaultInputModes?: string[];
  defaultOutputModes?: string[];
  security?: any[];
  securitySchemes?: Record<string, any>;
  signatures?: any[];
  supportsAuthenticatedExtendedCard?: boolean;
}

export interface Agent {
  agent_id: string;
  agent_card: AgentCard;
  is_online: boolean;
  last_seen: string;
}

export interface StoredAgentCard {
  id: string;
  agent_card: AgentCard;
  created_at: string;
  updated_at: string;
  last_online?: string;
}

export interface SearchResult {
  agent_id: string;
  agent_card: AgentCard;
  similarity_score?: number;
  matched_skills?: string[];
  matched_text?: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
}

// Backend response type that includes agent_id with the agent card
export interface AgentWithId extends AgentCard {
  agent_id: string;
}