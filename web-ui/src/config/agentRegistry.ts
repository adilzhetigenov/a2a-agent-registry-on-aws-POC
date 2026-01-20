/**
 * Configuration for Agent Registry Client
 */

export interface AgentRegistryConfig {
  apiGatewayUrl: string;
  region: string;
  identityPoolId?: string;
}

// Runtime environment interface for Docker deployment
declare global {
  interface Window {
    ENV?: {
      REACT_APP_API_GATEWAY_URL?: string;
      REACT_APP_AWS_REGION?: string;
      REACT_APP_IDENTITY_POOL_ID?: string;
    };
  }
}

/**
 * Get configuration from runtime environment (Docker) or build-time environment variables
 */
const getRuntimeConfig = (): AgentRegistryConfig => {
  // Try to get from runtime configuration (Docker deployment)
  const runtimeEnv = window.ENV;
  
  return {
    apiGatewayUrl: 
      runtimeEnv?.REACT_APP_API_GATEWAY_URL || 
      process.env.REACT_APP_API_GATEWAY_URL || 
      'https://api.agent-registry.example.com',
    region: 
      runtimeEnv?.REACT_APP_AWS_REGION || 
      process.env.REACT_APP_AWS_REGION || 
      'us-east-1',
    identityPoolId: 
      runtimeEnv?.REACT_APP_IDENTITY_POOL_ID || 
      process.env.REACT_APP_IDENTITY_POOL_ID,
  };
};

// Default configuration - supports both build-time and runtime environment variables
export const defaultConfig: AgentRegistryConfig = getRuntimeConfig();

// Validate configuration
export const validateConfig = (config: AgentRegistryConfig): void => {
  if (!config.apiGatewayUrl) {
    throw new Error('API Gateway URL is required. Set REACT_APP_API_GATEWAY_URL environment variable.');
  }

  if (!config.region) {
    throw new Error('AWS region is required. Set REACT_APP_AWS_REGION environment variable.');
  }

  try {
    new URL(config.apiGatewayUrl);
  } catch {
    throw new Error('Invalid API Gateway URL format.');
  }
};

/**
 * Get current configuration with runtime support
 */
export const getConfig = (): AgentRegistryConfig => {
  const config = getRuntimeConfig();
  validateConfig(config);
  return config;
};