> ## Documentation Index
> Fetch the complete documentation index at: https://docs.freyavoice.ai/llms.txt
> Use this file to discover all available pages before exploring further.

# List calls

> Returns calls for a workspace with filters, sorting, pagination, and export support.



## OpenAPI

````yaml https://staging-app.freyavoice.ai/api/openapi.json get /call
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
  /call:
    get:
      tags:
        - Calls
      summary: List calls
      description: >-
        Returns calls for a workspace with filters, sorting, pagination, and
        export support.
      operationId: listCalls
      parameters:
        - schema:
            type: string
            format: uuid
            description: Workspace identifier
          required: true
          description: Workspace identifier
          name: workspaceId
          in: query
        - schema:
            type: string
            default: '20'
            description: Page size (defaults to 20)
          required: false
          description: Page size (defaults to 20)
          name: limit
          in: query
        - schema:
            type: string
            default: '0'
            description: Offset for pagination
          required: false
          description: Offset for pagination
          name: offset
          in: query
        - schema:
            type: string
            enum:
              - startedAt
              - duration
              - sentiment
              - relativeTime
              - cost
            default: startedAt
            description: Sort field
          required: false
          description: Sort field
          name: sortBy
          in: query
        - schema:
            type: string
            enum:
              - asc
              - desc
            default: desc
            description: Sort direction
          required: false
          description: Sort direction
          name: sortOrder
          in: query
        - schema:
            type: string
            minLength: 1
            description: Comma-separated list of call IDs
          required: false
          description: Comma-separated list of call IDs
          name: callIds
          in: query
        - schema:
            type: string
            description: Filter calls starting at or after this ISO timestamp
          required: false
          description: Filter calls starting at or after this ISO timestamp
          name: startDate
          in: query
        - schema:
            type: string
            description: Filter calls starting before this ISO timestamp
          required: false
          description: Filter calls starting before this ISO timestamp
          name: endDate
          in: query
        - schema:
            type: string
            format: uuid
            description: Filter by phone number ID
          required: false
          description: Filter by phone number ID
          name: phoneNumberId
          in: query
        - schema:
            type: string
            description: Filter by customer phone number
          required: false
          description: Filter by customer phone number
          name: customerNumber
          in: query
        - schema:
            type: string
            format: uuid
            description: Filter by campaign ID
          required: false
          description: Filter by campaign ID
          name: campaignId
          in: query
        - schema:
            type: string
            description: Free text search
          required: false
          description: Free text search
          name: searchTerm
          in: query
        - schema:
            type: string
            description: Filter by call status
          required: false
          description: Filter by call status
          name: status
          in: query
        - schema:
            type: string
            description: Filter by call type
          required: false
          description: Filter by call type
          name: type
          in: query
        - schema:
            type: string
            description: Filter by ended reason
          required: false
          description: Filter by ended reason
          name: endedReason
          in: query
        - schema:
            type: string
            description: Base64-encoded filter state
          required: false
          description: Base64-encoded filter state
          name: filters
          in: query
        - schema:
            type: string
            description: Set to 'false' to skip status aggregation
          required: false
          description: Set to 'false' to skip status aggregation
          name: includeStatusCounts
          in: query
        - schema:
            type: string
            minLength: 2
            maxLength: 500
            description: Semantic (vector) search query - applied before filters
          required: false
          description: Semantic (vector) search query - applied before filters
          name: semanticQuery
          in: query
        - schema:
            type: string
            enum:
              - active
              - all
              - archived
            default: active
            description: Filter by archive status
          required: false
          description: Filter by archive status
          name: archivedFilter
          in: query
        - schema:
            type: string
            description: Set to 'true' to return a file export
          required: false
          description: Set to 'true' to return a file export
          name: export
          in: query
        - schema:
            type: string
            enum:
              - csv
              - xlsx
              - markdown
            description: Export file format
          required: false
          description: Export file format
          name: exportFormat
          in: query
        - schema:
            type: string
            description: JSON array of column definitions {id,label}
          required: false
          description: JSON array of column definitions {id,label}
          name: exportColumns
          in: query
        - schema:
            type: string
            description: 'Comma-separated extras: transcript,cxInsights'
          required: false
          description: 'Comma-separated extras: transcript,cxInsights'
          name: additionalData
          in: query
      responses:
        '200':
          description: Calls with pagination and status counts
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
                          calls:
                            type: array
                            items:
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
                                    name:
                                      type: string
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
                              required:
                                - id
                                - workspaceId
                          pagination:
                            type: object
                            properties:
                              total:
                                type: number
                              limit:
                                type: number
                              offset:
                                type: number
                              hasNext:
                                type: boolean
                              hasPrevious:
                                type: boolean
                            required:
                              - total
                              - limit
                              - offset
                              - hasNext
                              - hasPrevious
                          statusCounts:
                            type: object
                            properties:
                              all:
                                type: number
                              live:
                                type: number
                                default: 0
                              processing:
                                type: number
                                default: 0
                              transferred:
                                type: number
                              successful:
                                type: number
                              failed:
                                type: number
                            required:
                              - all
                              - transferred
                              - successful
                              - failed
                          searchTruncated:
                            type: boolean
                        required:
                          - calls
                          - pagination
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