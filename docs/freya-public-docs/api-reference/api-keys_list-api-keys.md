> ## Documentation Index
> Fetch the complete documentation index at: https://docs.freyavoice.ai/llms.txt
> Use this file to discover all available pages before exploring further.

# List API keys

> Returns all API keys for a workspace.



## OpenAPI

````yaml https://staging-app.freyavoice.ai/api/openapi.json get /api-keys
openapi: 3.1.0
info:
  title: Freyavoice API
  version: 2.0.0
  description: >-
    Production API for managing calls and campaigns.


    **Authentication**: All endpoints require a bearer token issued by
    Freyavoice.


    **Response Format**: All responses are wrapped in a standard envelope:

    ```json

    {
      "success": true,
      "data": {
        "message": "Success",
        "result": { /* endpoint-specific data */ }
      }
    }

    ```


    Error responses follow the same format with `success: false`:

    ```json

    {
      "success": false,
      "data": {
        "message": "Error description",
        "result": null
      }
    }

    ```
  contact:
    name: Freyavoice Support
    email: support@freyavoice.com
servers:
  - url: https://app.freyavoice.ai/api/v2
    description: Production
security: []
tags:
  - name: Agents
    description: Manage AI agents
  - name: Analytics
    description: Call analytics and metrics
  - name: API Keys
    description: API key management
  - name: Audio
    description: Audio transcription and speech synthesis
  - name: Calls
    description: Call management and history
  - name: Call Recordings
    description: Call recording management
  - name: Call Tags
    description: Call tagging and categorization
  - name: Campaigns
    description: Campaign management
  - name: Chat
    description: Stateful text chat with agents and workflows
  - name: Custom
    description: Custom convenience endpoints
  - name: Export
    description: Data export
  - name: Insights
    description: Structured data field definitions
  - name: Agent Insights
    description: Agent-to-field assignments
  - name: Integrations
    description: Third-party integrations
  - name: Personas
    description: Simulation personas for agent testing
  - name: Phone Numbers
    description: Phone number management
  - name: Phone Aliases
    description: Workspace phone book (phone-number to label mappings)
  - name: Suppression List
    description: Workspace do-not-call (DNC) list; numbers blocked from outbound dialing
  - name: Feedbacks
    description: Feedback tracking
  - name: Feedback Assignees
    description: Feedback assignment
  - name: Feedback Comments
    description: Feedback comments
  - name: Feedback References
    description: Feedback cross-references to other entities
  - name: Feedback Status Config
    description: Feedback status configuration
  - name: Reviews
    description: Call reviews
  - name: Review Assignees
    description: Review assignment
  - name: Simulations
    description: Agent simulation testing
  - name: Simulation Iterations
    description: Simulation iteration history
  - name: Unit Tests
    description: Behavioural unit tests for agents and workflows
  - name: Branches
    description: Branches (proposed changes) of an agent or workflow version line
  - name: Webhooks
    description: Webhook configuration
  - name: Versions
    description: Version history and rollback for agents and workflows
  - name: Workflows
    description: Workflow management
  - name: Workspaces
    description: Workspace management
  - name: Workspace Credits
    description: Workspace credit balance
  - name: Workspace Invitations
    description: Workspace invitations
  - name: Workspace Logs
    description: Workspace activity logs
  - name: Workspace Members
    description: Workspace member management
  - name: Workspace Roles
    description: Custom roles and permissions per workspace
  - name: Permissions
    description: Permission catalog (used by role + API-key UIs)
paths:
  /api-keys:
    get:
      tags:
        - API Keys
      summary: List API keys
      description: Returns all API keys for a workspace.
      operationId: listApiKeys
      parameters:
        - schema:
            type: string
            minLength: 1
            description: Workspace ID
          required: true
          description: Workspace ID
          name: workspaceId
          in: query
      responses:
        '200':
          description: API keys list
          content:
            application/json:
              schema:
                type: object
                properties:
                  success:
                    type: boolean
                    enum:
                      - true
                  data:
                    type: object
                    properties:
                      message:
                        type: string
                      result:
                        type: object
                        properties:
                          apiKeys:
                            type: array
                            items:
                              type: object
                              properties:
                                id:
                                  type: string
                                key:
                                  type: string
                                workspaceId:
                                  type: string
                                userId:
                                  type: string
                                name:
                                  type: string
                                isActive:
                                  type: boolean
                                createdAt:
                                  type: string
                                lastUsedAt:
                                  type:
                                    - string
                                    - 'null'
                                expiresAt:
                                  type: string
                                rateLimit:
                                  type: object
                                  properties:
                                    requestsPerMinute:
                                      type: integer
                                      exclusiveMinimum: 0
                                    requestsPerDay:
                                      type: integer
                                      exclusiveMinimum: 0
                                  required:
                                    - requestsPerMinute
                                    - requestsPerDay
                                permissions:
                                  type: array
                                  items:
                                    type: string
                                    enum:
                                      - agents:read
                                      - agents:write
                                      - agents:delete
                                      - agents:sync
                                      - agents:test
                                      - workflows:read
                                      - workflows:write
                                      - workflows:delete
                                      - workflows:sync
                                      - workflows:test
                                      - calls:read
                                      - calls:write
                                      - calls:delete
                                      - calls:import
                                      - calls:export
                                      - calls:recording-download
                                      - calls:metrics-read
                                      - calls:web-token
                                      - calls:chat-message
                                      - calls:cdr-read
                                      - calls:pii
                                      - calls:share
                                      - calls:register
                                      - calls:recording-upload
                                      - calls:transfer
                                      - calls:resume
                                      - calls:status-read
                                      - calls:webhook-payload
                                      - campaign:read
                                      - campaign:write
                                      - campaign:delete
                                      - campaign:execute
                                      - bes:read
                                      - bes:write
                                      - feedbacks:read
                                      - feedbacks:write
                                      - feedbacks:delete
                                      - feedbacks:comment
                                      - feedbacks:assign
                                      - feedbacks:config
                                      - reviews:read
                                      - reviews:write
                                      - reviews:delete
                                      - reviews:assign
                                      - insights:read
                                      - insights:write
                                      - insights:delete
                                      - insights:assign
                                      - assertions:read
                                      - assertions:write
                                      - assertions:delete
                                      - assertions:assign
                                      - personas:read
                                      - personas:write
                                      - personas:delete
                                      - simulations:read
                                      - simulations:write
                                      - simulations:delete
                                      - simulations:execute
                                      - solutions:read
                                      - solutions:write
                                      - solutions:delete
                                      - solutions:generate
                                      - solutions:accept
                                      - kb:read
                                      - kb:write
                                      - kb:delete
                                      - kb:upload
                                      - kb:sync
                                      - kb:articles-write
                                      - phone-numbers:read
                                      - phone-numbers:write
                                      - phone-numbers:delete
                                      - phone-numbers:import
                                      - phone-aliases:read
                                      - phone-aliases:write
                                      - phone-aliases:delete
                                      - suppression-list:read
                                      - suppression-list:write
                                      - suppression-list:delete
                                      - integrations:read
                                      - integrations:write
                                      - integrations:delete
                                      - integrations:webhook
                                      - analytics:read
                                      - analytics:widgets-write
                                      - analytics:widgets-delete
                                      - api-keys:read
                                      - api-keys:write
                                      - api-keys:delete
                                      - api-keys:manage-others
                                      - members:read
                                      - members:invite
                                      - members:remove
                                      - members:role-change
                                      - members:mfa-reset
                                      - roles:read
                                      - roles:write
                                      - roles:delete
                                      - billing:read
                                      - billing:manage
                                      - workspace:read
                                      - workspace:settings-write
                                      - workspace:delete
                                      - workspace:logs-read
                                      - versions:read
                                      - versions:publish
                                      - models:read
                                      - inbound:write
                                      - chat:read
                                      - custom:abbreviations-read
                                      - custom:abbreviations-write
                                      - speech-filter:preview
                                      - agents:resolve
                                      - campaign:resolve-contact
                                      - retention:purge
                                      - simulations:verdict-callback
                                  default: []
                                creator:
                                  type: object
                                  properties:
                                    id:
                                      type: string
                                    email:
                                      type:
                                        - string
                                        - 'null'
                                      format: email
                                    displayName:
                                      type:
                                        - string
                                        - 'null'
                                  required:
                                    - id
                              required:
                                - id
                                - key
                                - workspaceId
                                - userId
                                - name
                                - isActive
                                - createdAt
                                - expiresAt
                        required:
                          - apiKeys
                    required:
                      - message
                      - result
                required:
                  - success
                  - data
        '400':
          description: Validation error
          content:
            application/json:
              schema:
                type: object
                properties:
                  success:
                    type: boolean
                    enum:
                      - false
                  data:
                    type: object
                    properties:
                      message:
                        type: string
                      result: {}
                    required:
                      - message
                required:
                  - success
                  - data
        '401':
          description: Missing or invalid token
          content:
            application/json:
              schema:
                type: object
                properties:
                  success:
                    type: boolean
                    enum:
                      - false
                  data:
                    type: object
                    properties:
                      message:
                        type: string
                      result: {}
                    required:
                      - message
                required:
                  - success
                  - data
        '403':
          description: Workspace ID mismatch or insufficient permissions
          content:
            application/json:
              schema:
                type: object
                properties:
                  success:
                    type: boolean
                    enum:
                      - false
                  data:
                    type: object
                    properties:
                      message:
                        type: string
                      result: {}
                    required:
                      - message
                required:
                  - success
                  - data
        '500':
          description: Server error
          content:
            application/json:
              schema:
                type: object
                properties:
                  success:
                    type: boolean
                    enum:
                      - false
                  data:
                    type: object
                    properties:
                      message:
                        type: string
                      result: {}
                    required:
                      - message
                required:
                  - success
                  - data
      security:
        - bearerAuth: []
components:
  securitySchemes:
    bearerAuth:
      type: http
      scheme: bearer

````

This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.