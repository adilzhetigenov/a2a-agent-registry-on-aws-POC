# A2A Agent Registry on AWS — Deployment Journal

| | |
|---|---|
| **Project** | Agent Registry PoC — Ericsson Enterprise GenAI Platform |
| **Region** | eu-west-1 (Ireland) |
| **Account** | 905418281081 |

**Solution specs:** Agents self-register with skills/profile, and discover other agents by skills/profile — no human intervention.

---

## Phase 1 — Adapting the Open-Source Project

**Source:** [awslabs/a2a-agent-registry-on-aws](https://github.com/awslabs/a2a-agent-registry-on-aws)

**Original architecture:**
- AgentRegistryStack — API Gateway (IAM auth) + Lambda + S3 Vectors + Bedrock Titan Embeddings
- AgentRegistryWebUI — S3 + CloudFront + Cognito

**Changes required:**

| # | Issue | Fix |
|---|-------|-----|
| 1 | CDK CLI version mismatch | `npm install -g aws-cdk@latest` |
| 2 | No AWS credentials | SSO login with profile "Adil" |
| 3 | CDK not bootstrapped in eu-west-1 | `cdk bootstrap` |
| 4 | S3 Vectors unavailable in us-west-1 | Switched to eu-west-1 |
| 5 | cdk-nag suppressions hardcoded to us-east-1 | Dynamic region patterns |
| 6 | S3 Vectors rejects `aws:` prefixed tags | CDK Aspect to strip tags from `AWS::S3Vectors::*` |
| 7 | API GW CloudWatch logging failed | `cloudWatchRole: true` |
| 8 | `cdk.IConstruct` not found | Import from `constructs` package |

---

## Phase 2 — Deployment

### AgentRegistryStack (API)

**Status:** ✅ CREATE_COMPLETE

| Resource | Detail |
|----------|--------|
| API Gateway | `https://3mltf1n2wf.execute-api.eu-west-1.amazonaws.com/prod/` (IAM auth) |
| Lambda | Python 3.14, Bedrock + S3 Vectors access |
| S3 Vectors | 1024-dim cosine, Titan Embed Text v2 |

**Endpoints:**
| Method | Path | Description |
|--------|------|-------------|
| POST | /agents | Register agent |
| GET | /agents | List agents (paginated) |
| GET | /agents/{id} | Get agent |
| PUT | /agents/{id} | Update agent |
| DELETE | /agents/{id} | Delete agent |
| GET | /agents/search | Semantic + skill search |
| POST | /agents/{id}/health | Health heartbeat |

### AgentRegistryWebUI (Web UI)

**Status:** ✅ CREATE_COMPLETE

| Output | Value |
|--------|-------|
| WebUIUrl | `https://7y35dx3sch.execute-api.eu-west-1.amazonaws.com/ui` |
| WebUIApiEndpoint | `https://7y35dx3sch.execute-api.eu-west-1.amazonaws.com/ui/` |
| Cognito Console | `https://eu-west-1.console.aws.amazon.com/cognito/v2/idp/user-pools/eu-west-1_4ENWznDa4/users?region=eu-west-1` |
| Stack ARN | `arn:aws:cloudformation:eu-west-1:905418281081:stack/AgentRegistryWebUI/349053e0-2120-11f1-b8d6-02cef0a27e09` |

**Resources:** API Gateway (stage `/ui`) → Lambda (Python 3.12) → S3 (private), Cognito User Pool + Identity Pool, Config Generator Lambda

### CloudFront Workaround

Organization SCP blocked all CloudFront operations:

| Attempt | Blocked Action |
|---------|---------------|
| CloudFront + OAC | `cloudfront:CreateOriginAccessControl` |
| CloudFront + OAI | `cloudfront:CreateCloudFrontOriginAccessIdentity` |
| CloudFront alone | `cloudfront:CreateDistribution` |

**Solution:** Replaced CloudFront entirely with API Gateway + Lambda proxy that reads static files from S3, handles binary content (base64), and falls back to `index.html` for SPA routing.

### Post-Deployment Fixes

| # | Issue | Fix |
|---|-------|-----|
| 1 | Blank page | Rebuilt React with `PUBLIC_URL=/ui` (API GW stage path) |
| 2 | `aws-config.js` 404 | Changed script src to `%PUBLIC_URL%/aws-config.js` |
| 3 | "Forbidden" after sign-in | Cognito redirected to origin without `/ui` — fixed `AuthService.ts` redirects to include `process.env.PUBLIC_URL` |
| 4 | Callback URL mismatch | Added origin-only URLs to Cognito allowed callbacks |

### Final Architecture

```
Web UI:  Browser → API GW (/ui/) → Lambda → S3 (React)
         Browser → Cognito Hosted UI → Auth → Redirect /ui/

API:     SPA (SigV4) → API GW (/prod/) → Lambda → S3 Vectors + Bedrock
```

---

## Phase 3 — Cloudflare Integration (Planned)

### GenAI Platform Architecture

```
Human:   test.genai-innovation.ericsson.net → Cloudflare → MS Entra ID → cloudflared → OPA → EKS
Agent:   api.test.genai-innovation.ericsson.net → Cloudflare → cloudflared → OPA → EKS (no auth)
```

OPA = Agent Registry. Agents register and discover each other through it.

### Auth for Machine-to-Machine

| Option | Pros | Cons |
|--------|------|------|
| API Keys (API GW Usage Plan) | Simple, cross-environment | Key management |
| IRSA (EKS IAM roles) | No secrets, native AWS | Same-account only |

**Decision:** API Keys for PoC (agents may run across environments).

### Agent Lifecycle

```
Startup  → POST /agents (register name, skills, URL) → get agent_id
Running  → POST /agents/{id}/health (periodic heartbeat)
Discovery→ GET /agents/search?skills=python&text=financial+analysis → ranked results
Shutdown → DELETE /agents/{id}
```

### Target Integration

```
Human:  ericsson.net → Cloudflare → Entra ID → cloudflared → Web UI (API GW /ui/) → Cognito → API (SigV4)
Agent:  api.ericsson.net → Cloudflare → cloudflared → API (API GW /prod/) → API Key → S3 Vectors + Bedrock
```

### Next Steps

1. Add API Key / Usage Plan to AgentRegistryStack
2. Agent self-registration startup script for EKS pods
3. Cloudflare tunnel routing → API Gateway endpoints
4. End-to-end test: register → discover → collaborate
5. Health heartbeat in agent lifecycle

---

## Lessons Learned

| # | Lesson |
|---|--------|
| 1 | Check organizational SCPs early — CloudFront was blocked at every level |
| 2 | S3 Vectors: no `aws:` tags, limited regions — plan for workarounds |
| 3 | API GW stage paths affect everything: `PUBLIC_URL`, Cognito redirects, script paths |
| 4 | API GW + Lambda is a viable CloudFront alternative for internal PoC static hosting |
| 5 | Cognito callbacks need both full-path and origin-only URLs |
