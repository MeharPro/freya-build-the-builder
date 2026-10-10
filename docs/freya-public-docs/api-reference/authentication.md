> ## Documentation Index
> Fetch the complete documentation index at: https://docs.freyavoice.ai/llms.txt
> Use this file to discover all available pages before exploring further.

# Authentication

> Get your API key to start using the Freya APIs

All Freya API endpoints require a **Bearer token** for authentication. This token is tied to your workspace and can be generated from the dashboard.

## 1. Create an account

Head to [app.freyavoice.ai](https://app.freyavoice.ai) and sign up for a free account.

<Card title="Sign up for Freya" icon="arrow-up-right-from-square" href="https://app.freyavoice.ai">
  Create your account and workspace at app.freyavoice.ai
</Card>

## 2. Create a workspace

After signing in, you'll be prompted to create your first workspace. Workspaces are isolated environments — each one has its own agents, phone numbers, and API keys.

<Note>
  If you already have a workspace, you can skip this step and go straight to generating an API key.
</Note>

## 3. Generate an API key

Once inside your workspace:

<Steps>
  <Step title="Open API Keys">
    In the sidebar, scroll to the **Settings** section and click **API Keys**.
  </Step>

  <Step title="Create a new key">
    Click **Create API Key**, give it a name, and copy the generated token. Store it somewhere safe — it won't be shown again.
  </Step>
</Steps>

<Tip>
  You can also find a link to the API documentation directly on the API Keys page — click **View API Docs** next to the Create button.
</Tip>

## 4. Use the token in requests

Pass the token as a `Bearer` token in the `Authorization` header of every API request:

```bash theme={null}
Authorization: Bearer <your-api-key>
```

### Example

```bash theme={null}
curl -X POST "https://stt.freyavoice.ai/v1/audio/transcriptions" \
  -H "Authorization: Bearer <your-api-key>" \
  -F "file=@audio.wav"
```

<Warning>
  Never expose your API key in client-side code or public repositories. Use environment variables or a secrets manager to keep it secure.
</Warning>


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.