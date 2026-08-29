# Next Steps — Design Studio End-to-End Deployment

The current state ships **only** the conversational agent (AgentCore Runtime
container). The React frontend in `design_studio/frontend/` was originally
wired to a local FastAPI dev server (`server.py`) that held session/version
state in process memory.

**In production we drop FastAPI entirely.** Browsers shouldn't hold AWS
credentials and shouldn't talk to AgentCore directly — instead, a thin
**Lambda layer (Function URL or API Gateway, request/response)** sits
between the browser and AgentCore. The Lambda does two jobs for now:

1. Invokes AgentCore Runtime synchronously and returns the full agent
   response as JSON. **No streaming for now** — the agent's structured
   output (`vibe_options`, `theme_packages`, etc.) is small and
   request/response is simpler to debug.
2. Hosts the small REST endpoints that don't need an LLM (storefront fetch,
   version history, restore).

> **⚠️ Auth is intentionally deferred.** This roadmap ships **without
> authentication** — the Lambda Function URL is open behind CloudFront, and
> `merchantId` is sent by the client (e.g., as a header or path param). This
> is fine for an internal demo but **must not go to production as-is.** The
> auth model (Cognito User Pool, IdP federation, or something else) needs a
> team discussion. See [Adding auth later](#adding-auth-later) for the hooks
> already in place to make that swap painless.

This doc is the roadmap for getting the full app deployed.

> **Why still go through Lambda (even without auth)?**
> - Direct browser → AgentCore would still require AWS creds in the browser
>   (Cognito Identity Pool), so there's no "no auth" shortcut for that path.
> - With Lambda, the agent's IAM permissions stay server-side. Browser hits
>   plain HTTP, no AWS SDK in the bundle.
> - Gives you a place to add WAF, throttling, request validation, and
>   tenancy enforcement when auth lands later.
> - Same Lambda serves the small REST endpoints — one origin to manage.

> **Why no streaming (for now):** the agent returns structured JSON
> (`{ message, type, vibe_options?, theme_packages?, color_options? }`),
> not a long token stream a user reads as it arrives. Buffering the full
> response is fine UX-wise and removes a lot of complexity:
> `streamifyResponse`, SSE chunk handling on both sides, partial-JSON
> parsing, and CloudFront streaming behavior all go away. Easy to add
> later by switching the Lambda to `RESPONSE_STREAM` invoke mode if the
> agent ever streams meaningful incremental output.

> **Function URL or API Gateway?** Either works without streaming.
> Function URL is one less resource and pairs naturally with CloudFront
> origin behaviors. API Gateway gives you built-in throttling, request
> validation, and a more familiar surface. Defaulting to Function URL
> below for fewer moving parts — swap to API GW HTTP API if the team
> prefers it.

> **Why no FastAPI:** the dev server is a local-only convenience for hot
> reload and CORS. AgentCore + Lambda + DynamoDB cover every prod
> responsibility (HTTP, auth, scaling, persistence). A third HTTP service
> would duplicate all of that for no benefit.

> **Current deployed state (2026-05-15):**
> - `DesignStudioConversationalAgent` CDK stack in `eu-north-1`
> - `arn:aws:bedrock-agentcore:eu-north-1:111111111111:runtime/design_studio_conversational_agent-<runtime-id>`
> - `live` endpoint reachable, returns structured `AgentResponse` JSON
> - **Nothing else.** No frontend hosting, no auth, no persistence.

---

## TL;DR — what's missing

| Piece | Status | Where it lives now | Where it should live |
|---|---|---|---|
| Conversational agent | ✅ Deployed | AgentCore Runtime | (done) |
| Frontend static site | ❌ Not deployed | `frontend/dist/` (built locally) | S3 + CloudFront |
| User identity | ⏭️ **Deferred** | n/a (FastAPI is open) | TBD — needs team alignment |
| Browser ↔ backend transport | ❌ Not wired | `fetch('/api/...')` against FastAPI | CloudFront → Lambda Function URL (request/response) |
| Storefront/version state | ❌ In-process | `_agents`, `_histories`, `_versions` dicts in `server.py` | DynamoDB |
| `GET /storefront/{id}` | ❌ Not migrated | FastAPI returns rendered HTML | Lambda → DynamoDB |
| Undo / redo / restore | ❌ Not migrated | FastAPI in-memory list | Lambda → DynamoDB |
| `/screenshot/agentcore` | ❌ **No backend exists** | Frontend calls it; nothing serves it | Agent tool using **AgentCore Browser** → S3 → presigned URL |

---

## Architecture target

```
                          ┌──────────────────┐
                          │  Browser (SPA)   │
                          └────┬─────────┬───┘
                fetch /index   │         │ fetch /chat | /storefront | /versions
                               │         │   (X-Merchant-Id: <id>, no auth header)
                               ▼         ▼
                       ┌──────────────────────────┐
                       │ CloudFront               │
                       │  /        → S3 origin    │
                       │  /api/*   → Lambda URL   │
                       └─────┬──────────────┬─────┘
                             │              │
                             ▼              ▼
                    ┌──────────────┐   ┌──────────────────────┐
                    │  S3 (SPA)    │   │ Lambda Function URL  │
                    │  index.html  │   │  (request/response)  │
                    └──────────────┘   │                      │
                                       │  routes:             │
                                       │   POST /api/chat     │ ── invoke ──▶ AgentCore Runtime
                                       │   GET  /api/storefront/{id}           │
                                       │   GET  /api/versions/{id}             │  (boto3, IAM role)
                                       │   POST /api/restore                   │
                                       └─────────────┬────────┘                │
                                                     │                         ▼
                                                     │              ┌──────────────────┐
                                                     │              │ AgentCore        │
                                                     │              │ Runtime (chat)   │
                                                     │              │                  │
                                                     │              │ tool: screenshot │
                                                     │              │   ↓              │
                                                     │              │ AgentCore        │
                                                     │              │ Browser          │
                                                     │              │   ↓ PNG          │
                                                     │              │ S3 (artifacts)   │
                                                     │              └────────┬─────────┘
                                                     ▼                       │
                                            ┌─────────────────────────┐      │
                                            │ DynamoDB                │◀─────┘
                                            │ - StorefrontConfig      │  PK: merchantId
                                            │ - VersionHistory        │  PK: merchantId, SK: versionId
                                            │ - SessionState (TTL)    │  PK: sessionId
                                            └─────────────────────────┘
```

### Who serves what

| Frontend call | Served by | Notes |
|---|---|---|
| `POST /api/chat` | Lambda → AgentCore (sync) | Lambda reads `merchantId` from request header/body (auth deferred), invokes agent, returns the full response as JSON |
| `GET /api/storefront/{id}` | Lambda → DynamoDB | Pure read; no LLM |
| `GET /api/versions/{id}` | Lambda → DynamoDB | Pure query |
| `POST /api/restore` | Lambda → DynamoDB + agent state reset | Writes new "current" version |
| `POST /api/screenshot` | Agent **tool** (called inside `/api/chat`) | Agent uses AgentCore Browser; returns S3 presigned URL in chat response |

The SPA stays a single static bundle on S3+CloudFront. Browser only ever
hits CloudFront — no AWS SDK, no creds, no SigV4.

---

## Step-by-step

### 1. DynamoDB tables (new CDK stack: `DesignStudioDataStack`)

**Multi-tenancy model: pooled tables with IAM-enforced row isolation via
STS session tags.** The current implementation uses two shared tables
matching `DDB_Schema.md`. Merchant-scoped rows in `StorefrontStyle`
use `PK = MERCHANT#<merchantId>`. Per request, Lambda
calls `sts:AssumeRole` with a `merchantId` session tag; the assumed
role's policy uses `dynamodb:LeadingKeys` matching
`MERCHANT#${aws:PrincipalTag/merchantId}` to ensure the credentials can
only read/write that tenant's style rows.

Same compliance posture as silo'd per-tenant tables, without the
2,500-table soft limit, runtime `CreateTable` provisioning, or
per-tenant CDK stack count.

#### Tables

- **`StorefrontStyle`** — merchant-scoped style state.
  - PK: `PK` (string) — value `MERCHANT#<merchantId>`
  - SK: `SK` (string) — values such as `STYLE_PROFILE`, `STYLE#DRAFT`,
    `STYLE#PUBLISHED`, `STYLE#VERSION#0001`, `UNDO_STACK`, `ZONE_TOUR`,
    `PREVIEW#<token>`
  - GSIs: `type-updatedAt-index`, `previewToken-index`
  - TTL attribute: `ttl` for preview snapshots
  - Holds current draft/published tokens, version history, undo/redo state,
    zone tour progress, and future preview-link snapshots.
- **`ThemePackage`** — global starter packages.
  - PK: `packageId` (string)
  - Holds package metadata plus the same `tokens` blob shape as style items.

Both tables use on-demand billing, point-in-time recovery, and retained removal
policy in CDK. Starter theme package rows are seeded separately rather than by
the stack.

#### Per-tenant IAM enforcement (STS AssumeRole + session tags)

Each request to the Lambda derives a `merchantId` (from JWT claims later;
from the request body for now — see auth-deferred caveat). Lambda then
**assumes a tenant-scoped role via STS** before touching DynamoDB:

```python
import boto3, os

sts = boto3.client("sts")
TENANT_ROLE_ARN = os.environ["TENANT_DATA_ROLE_ARN"]

def tenant_ddb_client(merchant_id: str):
    creds = sts.assume_role(
        RoleArn=TENANT_ROLE_ARN,
        RoleSessionName=f"tenant-{merchant_id}",
        Tags=[{"Key": "merchantId", "Value": merchant_id}],
        # Tag is the trust mechanism — the role's policy checks it
        # against dynamodb:LeadingKeys via ${aws:PrincipalTag/merchantId}.
    )["Credentials"]
    return boto3.client(
        "dynamodb",
        aws_access_key_id=creds["AccessKeyId"],
        aws_secret_access_key=creds["SecretAccessKey"],
        aws_session_token=creds["SessionToken"],
    )
```

The tenant-scoped role's permissions policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:Query", "dynamodb:UpdateItem", "dynamodb:DeleteItem"],
    "Resource": [
      "arn:aws:dynamodb:eu-north-1:*:table/StorefrontStyle",
      "arn:aws:dynamodb:eu-north-1:*:table/StorefrontStyle/index/*"
    ],
    "Condition": {
      "ForAllValues:StringEquals": {
        "dynamodb:LeadingKeys": ["MERCHANT#${aws:PrincipalTag/merchantId}"]
      }
    }
  }, {
    "Effect": "Allow",
    "Action": ["dynamodb:GetItem", "dynamodb:Scan"],
    "Resource": "arn:aws:dynamodb:eu-north-1:*:table/ThemePackage"
  }]
}
```

Trust policy on the role — only the Lambda execution role can assume it,
**and only when it provides a `merchantId` session tag**:

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": { "AWS": "<lambda-execution-role-arn>" },
    "Action": ["sts:AssumeRole", "sts:TagSession"],
    "Condition": {
      "StringLike": { "aws:RequestTag/merchantId": "*" }
    }
  }]
}
```

The Lambda execution role itself has only `sts:AssumeRole` +
`sts:TagSession` on `TENANT_DATA_ROLE_ARN` — no direct DynamoDB
permissions.

**Net effect**: even if Lambda code has a bug that forgets the
`merchantId` filter on a Query, the IAM policy rejects the call. A
compromised tenant credential can only access that tenant's rows. No
cross-tenant data leak is possible at the AWS API layer.

**Caveat**: STS `AssumeRole` adds ~50ms per request. Cache credentials
in Lambda memory (boto3 `Session` keyed by merchantId, refresh ~1 min
before expiry) to amortize across warm invocations on the same container.

#### What gets passed to the agent

The agent (AgentCore Runtime) runs as a single shared container, not
per-tenant. To preserve isolation:

- Lambda assumes the tenant role and passes the **temporary credentials
  in the agent invoke payload** (transport is HTTPS via AgentCore;
  treat them as session-scoped, ~15min TTL):
  ```python
  payload = json.dumps({
      "message": ...,
      "merchant_id": merchant_id,
      "tenant_credentials": {
          "AccessKeyId": creds["AccessKeyId"],
          "SecretAccessKey": creds["SecretAccessKey"],
          "SessionToken": creds["SessionToken"],
      },
  }).encode()
  ```
- `agentcore_app.py` reads those creds and constructs a tenant-scoped
  boto3 session before calling tools that hit DynamoDB.
- The agent runtime role itself has **no DynamoDB permissions** — it
  can only act on tenant data through credentials Lambda hands it.

**Alternative if cred-passing feels brittle**: have the agent call back
to a small internal Lambda for DDB reads/writes. Slower, but no
cred-in-payload concern.

Pass the table names to **both** the agent runtime (env vars on `Runtime`)
**and** the Lambda (env vars on `PythonFunction`).

#### Caveat with auth deferred

Until JWT-derived `merchantId` is in place, the client asserts the
merchantId. The IAM enforcement still works — Lambda will dutifully
assume the role for whatever merchantId the client claims. **This is
isolation against bugs in your code, not against malicious clients.**
Once auth lands and the merchantId comes from a verified JWT, this
becomes a real security boundary.

#### Further reading

- **STS session tags → `aws:PrincipalTag`**:
  [Pass session tags in AWS STS](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_session-tags.html)
  (see "Using session tags for ABAC") and the
  [`AssumeRole` API reference](https://docs.aws.amazon.com/STS/latest/APIReference/API_AssumeRole.html).
- **DynamoDB row-level access control with `LeadingKeys`**:
  [Using IAM policy conditions for fine-grained access control](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/specifying-conditions.html).
- **SaaS multi-tenancy patterns this is based on**:
  [Multi-tenant microservices (Well-Architected SaaS Lens)](https://docs.aws.amazon.com/wellarchitected/latest/saas-lens/multi-tenant-microservices.html),
  [Token Vending Machine pattern (S3 example, same shape as our DDB approach)](https://docs.aws.amazon.com/prescriptive-guidance/latest/patterns/implement-saas-tenant-isolation-for-amazon-s3-by-using-an-aws-lambda-token-vending-machine.html),
  [Enforcing tenant isolation for agentic AI](https://docs.aws.amazon.com/prescriptive-guidance/latest/agentic-ai-multitenant/enforcing-tenant-isolation.html).

### 2. Refactor agent for stateless invocations

The agent currently writes to `storefront_config.json` on disk
(`config_manager.py` → `tools.py`). In a container, that file is per-instance
and disappears on scale-down.

- Replace `ConfigManager` filesystem reads/writes with DynamoDB calls keyed by
  `merchantId`. For now, the merchant ID comes from the client and is passed
  through Lambda → AgentCore in the invoke payload. **When auth lands**,
  Lambda will overwrite it from the JWT claims so the browser cannot spoof
  another tenant.
- The current `invoke()` signature in `runtime.py` takes `(message, session_id)`.
  Add `merchant_id` to the payload contract:
  ```python
  def invoke(message: str, session_id: str | None = None, merchant_id: str | None = None) -> dict:
  ```
  Update `agentcore_app.py` to read `payload.get("merchant_id")`. Reject
  invocations missing `merchant_id`. (Lambda is the trusted caller — it
  guarantees the field is present.)
- Tools that mutate config (`save_theme`, `customize_zone`, `reset_zone`,
  `reset_all`) need `merchant_id` injected. Pass it through closure when
  creating the agent: `create_agent(merchant_id=...)`.
- **No streaming for now.** Keep `agentcore_app.py`'s `@app.entrypoint`
  returning a plain `dict` (not an async generator). Lambda calls
  `invoke_agent_runtime` and reads the full response body in one shot.

### 3. Add the screenshot tool — AgentCore Browser

New CDK construct in the agent stack:

```ts
import * as agentcore from '@aws-cdk/aws-bedrock-agentcore-alpha';

const browser = new agentcore.BrowserCustom(this, 'StorefrontBrowser', {
  browserName: 'storefront_screenshot_browser',
  networkConfiguration: agentcore.BrowserNetworkConfiguration.public(),
  // Optional recording-to-S3 config; useful for debugging
});

browser.grantUse(runtime.role);  // agent can start browser sessions
```

In the agent code (`tools.py`), add a `take_screenshot` tool:

```python
@tool
def take_screenshot(url: str) -> str:
    """Render the current storefront and return an S3 presigned URL."""
    client = boto3.client("bedrock-agentcore", region_name="eu-north-1")
    session = client.start_browser_session(browserIdentifier=BROWSER_ID)
    # Use Playwright-over-CDP against session['streamUrl'] to navigate, screenshot
    # Upload PNG to S3 artifact bucket
    # Return presigned URL (15 min)
```

Frontend: drop the dedicated screenshot button. Add a chat button "Show me a
preview" that sends a message; the agent invokes `take_screenshot`, returns
the S3 URL in the chat response, and the SPA renders it inline.

**Why AgentCore Browser, not Playwright Lambda:**
- Already part of the same auth/IAM model — no separate runtime to manage.
- Anti-bot signing built in (`BrowserSigning.ENABLED`).
- Optional session recording to S3 for debugging.
- No 150MB layer maintenance, no Chromium cold starts in your Lambda.

### 4. Auth — DEFERRED ⏭️

Skipped pending team alignment. The Lambda Function URL will be open
(behind CloudFront only) and `merchantId` will be passed by the client.

**Mitigations while auth is off** (do all of these):

- **Lock CloudFront → Lambda to a shared secret.** Set a custom header
  (`X-CF-Origin-Secret: <random>`) in the CloudFront origin config and
  reject any Lambda invocation missing it. Stops attackers from hitting the
  Function URL directly if they discover its `*.lambda-url.*` domain.
- **WAF on CloudFront.** Rate-limit by IP, geo-restrict if applicable,
  block obvious abuse patterns. Cheap and works without auth.
- **Don't expose the deployed URL publicly.** Treat it as
  internal-demo-only.
- **No PII in DynamoDB.** Without auth there's no user identity to scope
  data anyway — keep it to theme JSON.

See [Adding auth later](#adding-auth-later) for what changes when this
gets unblocked.

### 5. Lambda backend (new CDK stack: `DesignStudioApiStack`)

One Lambda function, one Function URL, multiple routes:

- **Runtime**: Python 3.13 (matches the agent code).
- **Memory**: 512 MB is plenty for proxying JSON.
- **Timeout**: 60s (agent takes a few seconds; leave headroom).
- **Function URL config**:
  ```ts
  fn.addFunctionUrl({
    authType: lambda.FunctionUrlAuthType.NONE,  // CloudFront fronts it
    cors: { /* tightened to CloudFront only */ },
  });
  ```
  No `invokeMode` — defaults to buffered request/response.
- **Routing**: a tiny in-handler router (`event.rawPath`) is enough for 4
  endpoints. Don't pull in Express/Hono unless the surface grows.
- **Chat handler** (Python example, **no auth**):
  ```python
  import json, os, boto3

  agent_client = boto3.client("bedrock-agentcore", region_name="eu-north-1")

  def handler(event, _ctx):
      if event["headers"].get("x-cf-origin-secret") != os.environ["CF_ORIGIN_SECRET"]:
          return {"statusCode": 403, "body": "forbidden"}

      body = json.loads(event["body"])
      message = body["message"]
      session_id = body["sessionId"]
      merchant_id = body["merchantId"]
      # TODO(auth): when auth lands, replace `merchant_id` from body with
      # claims['custom:merchantId'] from a verified JWT.

      resp = agent_client.invoke_agent_runtime(
          agentRuntimeArn=os.environ["AGENT_RUNTIME_ARN"],
          qualifier="live",
          runtimeSessionId=session_id,
          payload=json.dumps({"message": message, "merchant_id": merchant_id}).encode(),
      )
      agent_response = resp["response"].read()  # full body, no streaming

      return {
          "statusCode": 200,
          "headers": {"content-type": "application/json"},
          "body": agent_response.decode(),
      }
  ```
- **IAM**: Lambda role gets `bedrock-agentcore:InvokeAgentRuntime` on the
  runtime ARN (only), `dynamodb:*Item`/`Query` on the three tables, and
  `s3:GetObject` for any artifact bucket.

### 6. Frontend changes

`frontend/src/App.jsx` currently calls `/api/...` — that's already what we
want. Keep this step focused on production transport and tenant/session
plumbing; preview screenshots are tracked separately.

- **Update the chat calls** to point at the new endpoint. Plain
  request/response, no streaming, no auth header — `merchantId` is sent
  in the body, along with a stable `sessionId`:
  ```js
  const res = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, sessionId, merchantId }),
  });
  const data = await res.json();
  appendMessage(data);  // { message, type, vibe_options?, ... }
  ```
- **No login UI** — the demo is open. `merchantId` can come from a URL
  query param (`?merchantId=demo-merchant`), localStorage, or be
  hardcoded for now. Mark this with a `TODO(auth)` comment so it's easy
  to find later.
- **Simplify backend selection** — there is no longer a user-visible
  backend choice, so keep one chat endpoint constant rather than
  `BACKEND_OPTIONS`.
- **Keep undo/redo/versions wired** now that Step 5 has landed. Use
  `GET /api/versions/{id}` and `POST /api/restore`, plus the existing
  undo/redo routes.

### 7. Frontend hosting (CDK stack: `DesignStudioFrontendStack`)

- `s3.Bucket` — `blockPublicAccess: BLOCK_ALL`, no static website hosting.
- `cloudfront.Distribution` with **two origins**:
  - **S3 origin** for `/*` (default) — uses Origin Access Control.
  - **HTTP origin** for `/api/*` pointing at the Lambda Function URL
    domain. Behavior overrides: `allowedMethods: ALL`, `cachePolicy:
    CACHING_DISABLED`, `originRequestPolicy: ALL_VIEWER_EXCEPT_HOST_HEADER`.
  - Default behavior: `CACHING_OPTIMIZED` for static assets,
    `CACHING_DISABLED` on `index.html`.
  - SPA fallback: `errorResponses: [{ httpStatus: 404, responseHttpStatus: 200, responsePagePath: '/index.html' }]`.
- `BucketDeployment` uploading `frontend/dist/` with
  `distribution: distribution, distributionPaths: ['/index.html']` to
  invalidate the entry point on each deploy.
- **Build step**: `cd frontend && npm run build` before `cdk deploy`.
  Either a `predeploy` npm script, or `Source.asset(..., { bundling })`.
- **Inject env vars** at build time: `VITE_REGION` (and Cognito IDs once
  auth lands). The Lambda URL is hidden behind CloudFront `/api/*` —
  frontend only knows its own origin.
- **Set the CloudFront → Lambda shared secret** as an origin custom header
  in the Lambda behavior. Generate it as a `secretsmanager.Secret` and
  pass to both CloudFront origin config and Lambda env (`CF_ORIGIN_SECRET`).

### 8. Wire the stacks together

`bin/cdk.ts` instantiates, in order:

1. `DesignStudioDataStack` — DynamoDB tables.
2. `DesignStudioConversationalAgent` (existing) — consumes table names as
   props, grants runtime role read/write, adds `BrowserCustom` for screenshots.
3. `DesignStudioApiStack` — Lambda + Function URL; consumes runtime ARN,
   table names, CloudFront-shared-secret.
4. `DesignStudioFrontendStack` — S3 + CloudFront with two origins
   (S3 + Function URL); consumes Lambda URL domain, injects shared secret
   as origin custom header.

(`DesignStudioAuthStack` slots in between 2 and 3 when auth lands.)

Cross-stack refs via `CfnOutput` + `Fn.importValue` or pass construct
references directly if everything is in one app.

### 9. Observability

The README already documents one-time CloudWatch Transaction Search setup
(applies to AgentCore traces). Add:

- CloudFront access logs to S3 + Athena.
- Lambda structured logs (JSON) → CloudWatch Logs Insights queries for
  `merchantId` × latency.
- Dashboards: agent invoke latency, Lambda duration p50/p99, DDB throttles,
  CloudFront 4xx/5xx by path.

---

## Adding auth later

When the team aligns on an auth model, here's the swap. The architecture
above was deliberately shaped so this drops in without re-plumbing.

1. **Add `DesignStudioAuthStack`**:
   - `cognito.UserPool` with email sign-in, MFA optional.
   - `cognito.UserPoolClient` for the SPA (no client secret, public client).
   - `cognito.UserPoolDomain` for hosted UI (or wire your own login form).
   - **Custom attribute** `merchantId` (immutable after first set, or use a
     Pre Token Generation Lambda to stamp it from an external directory).
   - Outputs: `UserPoolId`, `UserPoolClientId`, `Region`, `Domain`.

2. **Update Lambda** (`DesignStudioApiStack`):
   - In each handler, validate `event.headers.authorization` against the
     User Pool issuer URL.
   - Replace the `merchantId` from the request body with
     `claims['custom:merchantId']`. The `TODO(auth)` comment shows where.
   - Reject any request without a valid JWT.
   - **STS AssumeRole stays exactly the same** — see note below.

3. **Update frontend** (`App.jsx`):
   - Add hosted UI redirect (or Amplify Auth, or `oidc-client-ts`).
   - Store `idToken` in memory (not localStorage — XSS risk).
   - Refresh via Cognito's refresh token.
   - Add `Authorization: Bearer <idToken>` to every `/api/*` call.
   - Remove the `?merchantId=` URL param / hardcoded value.

4. **Decide on Identity Pool**: only needed if the browser ever needs to
   call AWS APIs directly (S3 uploads, Bedrock). Lambda hop covers
   everything in the current architecture, so probably skip.

5. **Tighten things you couldn't tighten before**: drop the
   CloudFront-Lambda shared secret in favor of "request must have a valid
   JWT" check, add per-tenant rate limits in WAF, etc.

The shared-secret check, request-validation, and CloudFront origin config
all stay — auth is additive.

#### Why STS AssumeRole stays even after auth lands

The Lambda execution role is **one static role serving all tenants**.
There is no IAM variable that reads "the merchantId from the JWT my
Lambda just verified" — IAM has no idea your Lambda ran a JWT
verification. The only way IAM sees a tenant identity is through a
session tag on temporary credentials, and session tags only exist on
STS-issued creds.

So the post-auth flow becomes:

```
Browser ──(JWT with custom:merchantId)──▶ Lambda
                                            │
                                            ├─ verify JWT → merchantId from claims
                                            │
                                            ├─ sts.assume_role(
                                            │     RoleArn=TENANT_ROLE,
                                            │     Tags=[{Key: merchantId, Value: <from JWT>}])
                                            │
                                            └─ ddb call with assumed creds
                                                → IAM enforces LeadingKeys
```

The only thing auth changes is **where the merchantId comes from**
before being stamped as a session tag (verified JWT instead of
client-supplied request body). The STS hop and the `LeadingKeys`
policy are unchanged.

What auth *does* improve: the "isolation against bugs only, not against
malicious clients" caveat from the data stack disappears. IAM
enforcement becomes a real security boundary because the merchantId is
now verifiable.

The only design where STS could be dropped is browser-held AWS creds
via Cognito **Identity Pool** (not User Pool) — those creds carry
`${cognito-identity.amazonaws.com:sub}` as a built-in IAM variable, no
AssumeRole needed. We rejected that path (browser-held AWS creds, no
Lambda hop for WAF/throttling/tenancy enforcement), so STS stays
permanently.

---

## Open questions for picking this up

1. **Session continuity**: AgentCore `runtimeSessionId` is per-conversation.
   How long do sessions live? Frontend should regenerate when the user
   clicks "new chat", reuse otherwise.
2. **Cleanup story**: `cdk destroy` should remove all resources, but
   DynamoDB data, S3 contents, and bootstrap ECR images survive by default.
   Decide retention policies (`RemovalPolicy.DESTROY` for demo, `RETAIN`
   for anything resembling prod).
3. **Auth (deferred)**: needs a team discussion. Open sub-questions:
   self-register vs. admin-provisioned, custom attribute vs. external
   directory, Cognito User Pool vs. corporate IdP, how `merchantId` maps
   to identity.
