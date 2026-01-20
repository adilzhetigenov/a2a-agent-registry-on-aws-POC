#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { AgentRegistryStack } from '../lib/agent-registry-stack';
import { AgentRegistryWebUI } from '../lib/agent-registry-web-ui-stack';
import { AwsSolutionsChecks } from 'cdk-nag';

const app = new cdk.App();

const env = {
  account: process.env.CDK_DEFAULT_ACCOUNT,
  region: process.env.CDK_DEFAULT_REGION,
};

// Agent Registry API stack
const agentRegistryStack = new AgentRegistryStack(app, 'AgentRegistryStack', {
  env,
});

// Web UI stack with CloudFront and Cognito
const webUIStack = new AgentRegistryWebUI(app, 'AgentRegistryWebUI', {
  env,
});

// Ensure Web UI stack depends on Agent Registry stack
webUIStack.addDependency(agentRegistryStack);

// Add cdk-nag AWS Solutions checks to validate security best practices
cdk.Aspects.of(app).add(new AwsSolutionsChecks({ verbose: true }));