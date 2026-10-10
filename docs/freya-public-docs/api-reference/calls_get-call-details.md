> ## Documentation Index
> Fetch the complete documentation index at: https://docs.freyavoice.ai/llms.txt
> Use this file to discover all available pages before exploring further.

# Get call details

> Returns detailed call information including transcript, messages, tags, and feedbacks.



## OpenAPI

````yaml https://staging-app.freyavoice.ai/api/openapi.json get /call/{callId}
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
  /call/{callId}:
    get:
      tags:
        - Calls
      summary: Get call details
      description: >-
        Returns detailed call information including transcript, messages, tags,
        and feedbacks.
      operationId: getCall
      parameters:
        - schema:
            type: string
            format: uuid
            description: Call ID
          required: true
          description: Call ID
          name: callId
          in: path
        - schema:
            type: string
            format: uuid
            description: Workspace ID
          required: true
          description: Workspace ID
          name: workspaceId
          in: query
      responses:
        '200':
          description: Call details
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
                          call:
                            type: object
                            properties:
                              id:
                                type: string
                              externalCallId:
                                type:
                                  - string
                                  - 'null'
                              assistantId:
                                type:
                                  - string
                                  - 'null'
                                format: uuid
                              assistantName:
                                type:
                                  - string
                                  - 'null'
                              assistantEntityType:
                                type:
                                  - string
                                  - 'null'
                                enum:
                                  - workflow
                                  - null
                              assistantWorkflowId:
                                type:
                                  - string
                                  - 'null'
                                format: uuid
                              workspaceId:
                                type: string
                              phoneNumberId:
                                type:
                                  - string
                                  - 'null'
                              phoneNumber:
                                type:
                                  - string
                                  - 'null'
                              simulationId:
                                type:
                                  - string
                                  - 'null'
                                format: uuid
                              campaign:
                                type:
                                  - object
                                  - 'null'
                                properties:
                                  id:
                                    type: string
                                  assistantId:
                                    type:
                                      - string
                                      - 'null'
                                    format: uuid
                                  phoneNumberId:
                                    type:
                                      - string
                                      - 'null'
                                  name:
                                    type: string
                                  description:
                                    type:
                                      - string
                                      - 'null'
                                required:
                                  - id
                                  - name
                              customerNumber:
                                type:
                                  - string
                                  - 'null'
                              customerLabel:
                                type:
                                  - string
                                  - 'null'
                              startedAt:
                                type:
                                  - string
                                  - 'null'
                              endedAt:
                                type:
                                  - string
                                  - 'null'
                              duration:
                                type:
                                  - number
                                  - 'null'
                              status:
                                type:
                                  - string
                                  - 'null'
                              type:
                                type:
                                  - string
                                  - 'null'
                              modality:
                                type:
                                  - string
                                  - 'null'
                                enum:
                                  - voice
                                  - text
                                  - null
                              endedReason:
                                type:
                                  - string
                                  - 'null'
                              transcript:
                                type:
                                  - string
                                  - 'null'
                              messages:
                                type:
                                  - array
                                  - 'null'
                                items:
                                  type: object
                                  properties:
                                    role:
                                      type: string
                                    message:
                                      type: string
                                    duration:
                                      type: number
                                    secondsFromStart:
                                      type: number
                                    timestamp:
                                      type: string
                                    endTime:
                                      type: number
                                    messageId:
                                      type: string
                                    was_blocked:
                                      type: boolean
                                    wasBlocked:
                                      type: boolean
                                    blocked_content:
                                      type: string
                                    blockedContent:
                                      type: string
                                  required:
                                    - role
                              summary:
                                type:
                                  - string
                                  - 'null'
                              cost:
                                type:
                                  - number
                                  - 'null'
                              turnLatencyStats:
                                type:
                                  - object
                                  - 'null'
                                properties:
                                  p50:
                                    type: number
                                  p75:
                                    type: number
                                  p90:
                                    type: number
                                  p95:
                                    type: number
                                  p99:
                                    type: number
                                  avg:
                                    type:
                                      - number
                                      - 'null'
                                  count:
                                    type: number
                                required:
                                  - p50
                                  - p75
                                  - p95
                                  - p99
                              recordingUrl:
                                type:
                                  - string
                                  - 'null'
                              tags:
                                type: array
                                items:
                                  type: object
                                  properties:
                                    tag:
                                      type: string
                                    source:
                                      type: string
                                    value:
                                      type: number
                                    confidence:
                                      type:
                                        - number
                                        - 'null'
                                      minimum: 0
                                      maximum: 1
                                    metadata:
                                      type:
                                        - object
                                        - 'null'
                                      additionalProperties: {}
                                  required:
                                    - tag
                                    - source
                                  additionalProperties: false
                              customer:
                                type: object
                                properties:
                                  number:
                                    type:
                                      - string
                                      - 'null'
                                  identity:
                                    type: object
                                    properties:
                                      firstName:
                                        type: string
                                      lastName:
                                        type: string
                                      email:
                                        type: string
                              unresolvedFeedbacksCount:
                                type: number
                              resolvedFeedbacksCount:
                                type: number
                              unresolvedAiFeedbacksCount:
                                type: number
                              unresolvedUserFeedbacksCount:
                                type: number
                              reviewStatus:
                                type:
                                  - string
                                  - 'null'
                              reviewTag:
                                type:
                                  - string
                                  - 'null'
                              reviewNotes:
                                type:
                                  - string
                                  - 'null'
                              reviewAssignees:
                                type:
                                  - array
                                  - 'null'
                                items:
                                  type: object
                                  properties:
                                    userId:
                                      type: string
                                    userName:
                                      type:
                                        - string
                                        - 'null'
                                  required:
                                    - userId
                              isArchived:
                                type: boolean
                                default: false
                              isImported:
                                type: boolean
                                default: false
                              isShared:
                                type: boolean
                              assertionsSummary:
                                type:
                                  - object
                                  - 'null'
                                properties:
                                  passed:
                                    type: number
                                  failed:
                                    type: number
                                  total:
                                    type: number
                                required:
                                  - passed
                                  - failed
                                  - total
                              unitTestsCount:
                                type: number
                              searchScore:
                                type: number
                              searchSnippet:
                                type: string
                              entityVersionId:
                                type:
                                  - string
                                  - 'null'
                                format: uuid
                              entityVersionNumber:
                                type:
                                  - number
                                  - 'null'
                              updatedAt:
                                type:
                                  - string
                                  - 'null'
                              sipCallId:
                                type:
                                  - string
                                  - 'null'
                              analysis: {}
                              createdAt:
                                type:
                                  - string
                                  - 'null'
                              artifact: {}
                              problems:
                                type: array
                                items:
                                  type: object
                                  properties:
                                    id:
                                      type: string
                                    workspaceId:
                                      type:
                                        - string
                                        - 'null'
                                    callId:
                                      type:
                                        - string
                                        - 'null'
                                      format: uuid
                                    agentId:
                                      type:
                                        - string
                                        - 'null'
                                      format: uuid
                                    title:
                                      type: string
                                      minLength: 1
                                    description:
                                      type:
                                        - string
                                        - 'null'
                                    proposedSolution:
                                      type:
                                        - string
                                        - 'null'
                                    solutionNote:
                                      type:
                                        - string
                                        - 'null'
                                    type:
                                      type:
                                        - string
                                        - 'null'
                                      enum:
                                        - workflow
                                        - decision-llm
                                        - stt
                                        - tts
                                        - vad-nc
                                        - latency
                                        - platform
                                        - ui
                                        - general
                                        - null
                                    severity:
                                      type: number
                                      minimum: 0
                                      maximum: 1
                                      default: 0.5
                                    status:
                                      type: string
                                      default: open
                                    assignedTo:
                                      type:
                                        - string
                                        - 'null'
                                    createdBy:
                                      type: string
                                      default: ai
                                    messageId:
                                      type:
                                        - string
                                        - 'null'
                                    resolved:
                                      type: boolean
                                      default: false
                                    resolvedAt:
                                      type:
                                        - string
                                        - 'null'
                                    resolvedBy:
                                      type:
                                        - string
                                        - 'null'
                                    solutionId:
                                      type:
                                        - string
                                        - 'null'
                                      format: uuid
                                    resolvedByVersionId:
                                      type:
                                        - string
                                        - 'null'
                                      format: uuid
                                    number:
                                      type:
                                        - integer
                                        - 'null'
                                    createdAt:
                                      type: string
                                    updatedAt:
                                      type: string
                                    callStartedAt:
                                      type:
                                        - string
                                        - 'null'
                                    customerNumber:
                                      type:
                                        - string
                                        - 'null'
                                    entityVersionId:
                                      type:
                                        - string
                                        - 'null'
                                      format: uuid
                                    versionNumber:
                                      type:
                                        - integer
                                        - 'null'
                                    callReviewTag:
                                      type:
                                        - string
                                        - 'null'
                                    callReviewNotes:
                                      type:
                                        - string
                                        - 'null'
                                    webCallerName:
                                      type:
                                        - string
                                        - 'null'
                                    webCallerUserId:
                                      type:
                                        - string
                                        - 'null'
                                    hasExternalReference:
                                      type: boolean
                                    externalReferences:
                                      type: array
                                      items:
                                        type: object
                                        properties:
                                          id:
                                            type: string
                                          url:
                                            type: string
                                          label:
                                            type:
                                              - string
                                              - 'null'
                                        required:
                                          - id
                                          - url
                                          - label
                                    agentName:
                                      type:
                                        - string
                                        - 'null'
                                    agentEntityType:
                                      type:
                                        - string
                                        - 'null'
                                    agentWorkflowId:
                                      type:
                                        - string
                                        - 'null'
                                    resolvedByName:
                                      type:
                                        - string
                                        - 'null'
                                    assignees:
                                      type: array
                                      items:
                                        type: object
                                        properties:
                                          userId:
                                            type: string
                                          userName:
                                            type:
                                              - string
                                              - 'null'
                                          assignedAt:
                                            type: string
                                        required:
                                          - userId
                                          - assignedAt
                                    commentsCount:
                                      type: number
                                    openSolutions:
                                      type: array
                                      items:
                                        type: object
                                        properties:
                                          branchId:
                                            type: string
                                          name:
                                            type: string
                                          entityType:
                                            type: string
                                          entityId:
                                            type: string
                                        required:
                                          - branchId
                                          - name
                                          - entityType
                                          - entityId
                                    isArchived:
                                      type: boolean
                                      default: false
                                  required:
                                    - title
                              assertionResults:
                                type: array
                                items:
                                  type: object
                                  properties:
                                    id:
                                      type: string
                                    name:
                                      type: string
                                    assertion:
                                      type: string
                                    success:
                                      type:
                                        - boolean
                                        - 'null'
                                    reason:
                                      type:
                                        - string
                                        - 'null'
                                    relevantMessages:
                                      type: object
                                      additionalProperties:
                                        type: string
                                    timeTaken:
                                      type:
                                        - number
                                        - 'null'
                                    metadata:
                                      type: object
                                      additionalProperties: {}
                              successCriteriaResult:
                                type: object
                                properties:
                                  id:
                                    type: string
                                  name:
                                    type: string
                                  assertion:
                                    type: string
                                  success:
                                    type:
                                      - boolean
                                      - 'null'
                                  reason:
                                    type:
                                      - string
                                      - 'null'
                                  relevantMessages:
                                    type: object
                                    additionalProperties:
                                      type: string
                                  timeTaken:
                                    type:
                                      - number
                                      - 'null'
                                  metadata:
                                    type: object
                                    additionalProperties: {}
                            required:
                              - id
                              - workspaceId
                        required:
                          - call
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
        '404':
          description: Call not found
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