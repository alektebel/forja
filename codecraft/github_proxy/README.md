# GitHub sign-in proxy

`forja` is a static page. GitHub's device endpoints (`/login/device/code` and
`/login/oauth/access_token`) do not answer CORS, so the browser cannot call
them directly. This directory holds the only server-side piece: a Lambda that
forwards those two calls and adds CORS. It needs **no client secret**; device
flow uses only the OAuth App's public client ID.

```
browser ──POST /device──────────► Lambda ──► github.com/login/device/code
browser ──POST /token───────────► Lambda ──► github.com/login/oauth/access_token
browser ──GET  api.github.com/user (CORS is enabled by GitHub) ──► profile
```

The client lives in `codecraft/web/app.js` (`ghSignIn`, `ghPoll`) and reads the
proxy base URL from `<meta name="forja-github-proxy">` in
`codecraft/web/index.html`. Empty meta leaves the button as a setup prompt.

## One-time setup

1. **Create the OAuth App** at <https://github.com/settings/applications/new>.
   - Homepage URL: `https://diegoatencia.dev/forja/`
   - Authorization callback URL: `https://diegoatencia.dev/forja/` (unused by
     device flow)
   - After creating it, tick **Enable Device Flow** on the app page.
   - Copy the **Client ID** (public; the client secret is not used anywhere).

2. **Package and upload the Lambda**:

   ```sh
   cd codecraft/github_proxy
   zip github-device.zip app.py
   aws s3 cp github-device.zip s3://<CodeBucket>/github-device/github-device.zip
   ```

3. **Deploy the stack** (plain CloudFormation, no SAM transform):

   ```sh
   aws cloudformation deploy \
     --template-file template-github-cfn.yaml \
     --stack-name forja-github-device \
     --parameter-overrides \
       CodeBucket=<CodeBucket> \
       CodeKey=github-device/github-device.zip \
       GithubClientId=<ClientID> \
     --capabilities CAPABILITY_IAM
   ```

4. **Read the endpoint** and put it in the page meta:

   ```sh
   aws cloudformation describe-stacks --stack-name forja-github-device \
     --query 'Stacks[0].Outputs[?OutputKey==`GithubProxyEndpoint`].OutputValue' \
     --output text
   ```

   ```html
   <meta name="forja-github-proxy" content="https://<api-id>.execute-api.<region>.amazonaws.com">
   ```

   Commit and push the forja repo; CI bakes it into the site.

## API contract

Both routes take and return JSON. The proxy supplies `client_id` and locks
`scope` to `read:user`; the browser cannot widen either.

| Route | Request | Response |
|---|---|---|
| `POST /device` | `{}` | GitHub's `{device_code, user_code, verification_uri, expires_in, interval}` (or `{error}`) |
| `POST /token` | `{"device_code":"..."}` | GitHub's `{access_token, token_type, scope}` or `{error:"authorization_pending"}` etc. |
| `GET /` | — | `{"ok":true}` smoke test |

CORS is answered by `app.py` for `OPTIONS` and every response. Allowed origins
come from `ALLOWED_ORIGIN` (defaults include `https://diegoatencia.dev`,
`https://alektebel.github.io`, and `http://127.0.0.1:8875` for `serve.py`).

## Notes

- The access token is kept in `localStorage` (`forja.github`) and used to call
  `api.github.com/user`. It is a bearer credential: any XSS on the page can
  read it. Scope is limited to `read:user`.
- The proxy sees the token in transit because it forwards GitHub's response.
  Responses are `no-store` and nothing is logged.
- Device-flow codes expire after ~15 minutes; the page handles
  `authorization_pending`, `slow_down`, `expired_token`, and `access_denied`.
- To test the handler locally without AWS, call `app.lambda_handler` with a
  minimal API Gateway v2 event (see the routes above); set
  `GITHUB_CLIENT_ID` to the OAuth App client ID.
