# Retrieval Evaluation V2 — Author Review Packet

> Status: approved and frozen by the project author on 2026-09-21. Each checked row means its requirement,
> relevant labels, support levels, quotes, hard negatives, and rationale are approved.
> This packet contains no retrieval rankings or holdout metrics.

## How to respond

Use `approve all`, or list changes by query ID. Examples:

- `611...0002: approve`
- `611...0006: change 111...0009 from partial to full`
- `833...0004: remove relevant 333...0006`
- `Experience 222...0005: rewrite description to ...`

## Part A — Synthetic Experience corpus (40)

### Profile: `backend-platform` — Synthetic student focused on backend services and platform reliability.

- [x] **E1. Order API** — `11111111-1111-4111-8111-000000000001`
  - Kind: `project`
  - Description: Built a Python FastAPI order service with PostgreSQL transactions and idempotency keys to prevent duplicate orders.
  - Skills: Python, FastAPI, PostgreSQL, idempotency
  - Outcome: Passed deterministic concurrent-request tests.

- [x] **E2. Event Processing Internship** — `11111111-1111-4111-8111-000000000002`
  - Kind: `work`
  - Description: Implemented Java Kafka consumers with retry topics and a dead-letter queue for malformed events.
  - Skills: Java, Kafka, event-driven systems
  - Outcome: Reduced manual replay work in the synthetic team scenario.

- [x] **E3. Container Delivery Pipeline** — `11111111-1111-4111-8111-000000000003`
  - Kind: `project`
  - Description: Packaged a service with Docker and deployed it to Kubernetes through GitHub Actions with health checks and rollback steps.
  - Skills: Docker, Kubernetes, GitHub Actions, CI/CD
  - Outcome: Documented a repeatable deployment and rollback runbook.

- [x] **E4. Authorization Service** — `11111111-1111-4111-8111-000000000004`
  - Kind: `project`
  - Description: Added OAuth2 login, JWT validation, and role-based authorization checks at API and repository boundaries.
  - Skills: OAuth2, JWT, RBAC, authorization
  - Outcome: Cross-user access tests rejected unauthorized reads and writes.

- [x] **E5. Dashboard Cache** — `11111111-1111-4111-8111-000000000005`
  - Kind: `project`
  - Description: Implemented a Redis cache that fails open to PostgreSQL when Redis is unavailable or returns malformed JSON.
  - Skills: Redis, PostgreSQL, caching, resilience
  - Outcome: Verified cache failure paths with deterministic integration tests.

- [x] **E6. Concurrent Rate Limiter** — `11111111-1111-4111-8111-000000000006`
  - Kind: `course`
  - Description: Wrote a Go token-bucket rate limiter and tested concurrent clients for race-free quota enforcement.
  - Skills: Go, concurrency, rate limiting
  - Outcome: The race detector reported no data races in the course workload.

- [x] **E7. Serverless Notification Worker** — `11111111-1111-4111-8111-000000000007`
  - Kind: `project`
  - Description: Processed notification jobs with AWS Lambda and SQS, using DynamoDB conditional writes for deduplication.
  - Skills: AWS Lambda, SQS, DynamoDB, serverless
  - Outcome: Duplicate deliveries were suppressed in local integration fixtures.

- [x] **E8. Query Tuning Lab** — `11111111-1111-4111-8111-000000000008`
  - Kind: `course`
  - Description: Used PostgreSQL EXPLAIN ANALYZE and composite indexes to optimize joins over application and task tables.
  - Skills: SQL, PostgreSQL, query optimization, indexing
  - Outcome: Saved before-and-after query plans for review.

- [x] **E9. Payment Ledger** — `11111111-1111-4111-8111-000000000009`
  - Kind: `project`
  - Description: Designed a payment ledger with database unique constraints and serializable transactions to preserve account balances.
  - Skills: transactions, database constraints, concurrency control
  - Outcome: Concurrent debit tests preserved the balance invariant.

- [x] **E10. GraphQL Catalog** — `11111111-1111-4111-8111-000000000010`
  - Kind: `project`
  - Description: Created a Node.js GraphQL catalog API and documented Rust as a possible future rewrite without implementing it.
  - Skills: Node.js, GraphQL, API design
  - Outcome: None

### Profile: `data-ai` — Synthetic student focused on data platforms and applied machine learning.

- [x] **E1. Analytics Warehouse Pipeline** — `22222222-2222-4222-8222-000000000001`
  - Kind: `project`
  - Description: Orchestrated daily Python ETL jobs with Airflow and modeled validated warehouse tables with dbt and Snowflake, blocking incomplete loads before table updates.
  - Skills: Python, Airflow, dbt, Snowflake, ETL
  - Outcome: Data quality checks blocked incomplete daily loads.

- [x] **E2. Evidence Retrieval Research** — `22222222-2222-4222-8222-000000000002`
  - Kind: `research`
  - Description: Built a Python retrieval-augmented generation prototype with text embeddings and labeled Recall@K evaluation cases.
  - Skills: Python, RAG, embeddings, retrieval evaluation
  - Outcome: Recorded reproducible offline evaluation artifacts.

- [x] **E3. Model Experiment Registry** — `22222222-2222-4222-8222-000000000003`
  - Kind: `project`
  - Description: Tracked scikit-learn experiments with MLflow and packaged reproducible training jobs in Docker.
  - Skills: scikit-learn, MLflow, Docker, MLOps
  - Outcome: A clean environment reproduced the selected model artifact.

- [x] **E4. Streaming Feature Pipeline** — `22222222-2222-4222-8222-000000000004`
  - Kind: `project`
  - Description: Processed Kafka events with Spark Structured Streaming, wrote windowed aggregates to a feature table, and exercised late events with deterministic fixtures.
  - Skills: Kafka, Spark, stream processing
  - Outcome: Late events were exercised with deterministic fixtures.

- [x] **E5. Feature Store Prototype** — `22222222-2222-4222-8222-000000000005`
  - Kind: `project`
  - Description: Served versioned machine-learning features through Feast with Redis online storage and rejected stale features through freshness validation.
  - Skills: Feast, Redis, feature stores, data validation
  - Outcome: Rejected stale features in integration tests.

- [x] **E6. Demand Forecasting** — `22222222-2222-4222-8222-000000000006`
  - Kind: `course`
  - Description: Trained scikit-learn time-series baselines and evaluated them with rolling temporal validation.
  - Skills: scikit-learn, time series, forecasting
  - Outcome: Compared models without leaking future observations.

- [x] **E7. Image Classification Lab** — `22222222-2222-4222-8222-000000000007`
  - Kind: `course`
  - Description: Fine-tuned a TensorFlow image classifier and analyzed class-level confusion matrices.
  - Skills: TensorFlow, computer vision, model evaluation
  - Outcome: Documented failure cases for minority classes.

- [x] **E8. Data Contract Monitor** — `22222222-2222-4222-8222-000000000008`
  - Kind: `project`
  - Description: Created Great Expectations checks for schema drift, missing values, and invalid categorical fields.
  - Skills: Great Expectations, data quality, schema validation
  - Outcome: Invalid batches failed before reaching analytics tables.

- [x] **E9. Operations Analytics** — `22222222-2222-4222-8222-000000000009`
  - Kind: `work`
  - Description: Wrote documented SQL transformations and built Tableau dashboards whose charts were traceable to those queries.
  - Skills: SQL, Tableau, analytics
  - Outcome: Stakeholders could trace each chart to a documented query.

- [x] **E10. Privacy Reading Group** — `22222222-2222-4222-8222-000000000010`
  - Kind: `research`
  - Description: Presented papers about differential privacy but did not implement a privacy-preserving training system.
  - Skills: research communication, machine learning privacy
  - Outcome: None

### Profile: `frontend-mobile` — Synthetic student focused on accessible web and mobile product engineering.

- [x] **E1. Accessible React Dashboard** — `33333333-3333-4333-8333-000000000001`
  - Kind: `project`
  - Description: Built a React and TypeScript dashboard with keyboard navigation, semantic HTML, and automated accessibility checks.
  - Skills: React, TypeScript, accessibility
  - Outcome: Resolved all violations in the checked component set.

- [x] **E2. Next.js Storefront** — `33333333-3333-4333-8333-000000000002`
  - Kind: `project`
  - Description: Implemented a Next.js storefront with server-side rendering, route-level caching, and structured metadata.
  - Skills: Next.js, React, SSR, SEO
  - Outcome: Verified rendered metadata and cache behavior in tests.

- [x] **E3. Offline Field App** — `33333333-3333-4333-8333-000000000003`
  - Kind: `project`
  - Description: Developed a React Native field app with an offline queue and conflict-aware synchronization after reconnection; recovery tests preserved locally entered records across network loss.
  - Skills: React Native, offline-first, synchronization
  - Outcome: Recovery tests preserved locally entered records.

- [x] **E4. Android Campus Map** — `33333333-3333-4333-8333-000000000004`
  - Kind: `course`
  - Description: Created a Kotlin Android application with Jetpack Compose, location permissions, and cached map markers.
  - Skills: Kotlin, Android, Jetpack Compose
  - Outcome: Handled denied location permissions without crashing.

- [x] **E5. iOS Study Timer** — `33333333-3333-4333-8333-000000000005`
  - Kind: `project`
  - Description: Built a SwiftUI study timer with local notifications and persisted session history using Core Data.
  - Skills: Swift, SwiftUI, Core Data, iOS
  - Outcome: Timer state survived application restarts.

- [x] **E6. Component Library** — `33333333-3333-4333-8333-000000000006`
  - Kind: `work`
  - Description: Maintained reusable TypeScript components in Storybook with design tokens and visual regression tests, documenting component states and accessibility expectations.
  - Skills: TypeScript, Storybook, design systems, testing
  - Outcome: Documented component states and accessibility expectations.

- [x] **E7. Web Performance Audit** — `33333333-3333-4333-8333-000000000007`
  - Kind: `project`
  - Description: Reduced client JavaScript through code splitting, lazy loading, and image optimization, then profiled Core Web Vitals.
  - Skills: web performance, code splitting, Core Web Vitals
  - Outcome: Saved Lighthouse traces rather than claiming an unverified production improvement.

- [x] **E8. Checkout Browser Tests** — `33333333-3333-4333-8333-000000000008`
  - Kind: `project`
  - Description: Wrote Playwright end-to-end tests for checkout, failed payments, and keyboard-only navigation.
  - Skills: Playwright, end-to-end testing, accessibility testing
  - Outcome: The suite covered successful and failed checkout paths.

- [x] **E9. Frontend Backend-for-Frontend** — `33333333-3333-4333-8333-000000000009`
  - Kind: `project`
  - Description: Implemented a Node.js Express backend-for-frontend that aggregated PostgreSQL data for a React client.
  - Skills: Node.js, Express, PostgreSQL, API integration
  - Outcome: Contract tests protected the client response shape.

- [x] **E10. Bilingual Interface** — `33333333-3333-4333-8333-000000000010`
  - Kind: `project`
  - Description: Localized a web interface in English and Chinese with ICU message formatting, locale-aware dates, and missing-translation fallbacks.
  - Skills: internationalization, localization, Chinese, English
  - Outcome: Language-switch tests covered missing translation fallbacks.

### Profile: `systems-research` — Synthetic student focused on low-level systems and computer science research.

- [x] **E1. LSM Storage Engine** — `44444444-4444-4444-8444-000000000001`
  - Kind: `project`
  - Description: Implemented a C++ log-structured merge storage engine with write-ahead logging, compaction, and concurrent reads.
  - Skills: C++, storage engines, concurrency
  - Outcome: Crash-recovery tests restored committed records.

- [x] **E2. Async Network Server** — `44444444-4444-4444-8444-000000000002`
  - Kind: `project`
  - Description: Built a Rust asynchronous TCP server with Tokio, bounded queues, and graceful shutdown.
  - Skills: Rust, Tokio, network programming, async
  - Outcome: Load fixtures verified bounded backpressure behavior.

- [x] **E3. Teaching Kernel** — `44444444-4444-4444-8444-000000000003`
  - Kind: `course`
  - Description: Modified a C teaching kernel to implement priority scheduling and copy-on-write process memory.
  - Skills: C, operating systems, scheduling, virtual memory
  - Outcome: Kernel tests covered starvation and page-fault paths.

- [x] **E4. Replicated Key-Value Store** — `44444444-4444-4444-8444-000000000004`
  - Kind: `research`
  - Description: Implemented Raft leader election and log replication in Go for a replicated key-value store.
  - Skills: Go, Raft, distributed systems, consensus
  - Outcome: Fault-injection tests covered leader loss and log repair.

- [x] **E5. LLVM Compiler Pass** — `44444444-4444-4444-8444-000000000005`
  - Kind: `course`
  - Description: Wrote an LLVM optimization pass in C++ and used regression tests against reference outputs to detect incorrect transformations.
  - Skills: LLVM, C++, compilers, program analysis
  - Outcome: Regression tests detected incorrect transformations.

- [x] **E6. CUDA Matrix Kernels** — `44444444-4444-4444-8444-000000000006`
  - Kind: `research`
  - Description: Optimized CUDA matrix kernels using shared memory, coalesced access, and occupancy profiling.
  - Skills: CUDA, GPU programming, parallel computing
  - Outcome: Stored profiler traces for each kernel variant.

- [x] **E7. Protocol Fuzzing** — `44444444-4444-4444-8444-000000000007`
  - Kind: `research`
  - Description: Created coverage-guided fuzz tests in C++ for a binary protocol parser, minimized crashing inputs, and added regression fixtures for every minimized crash.
  - Skills: C++, fuzzing, security testing
  - Outcome: Added regression fixtures for every minimized crash.

- [x] **E8. Approximate Nearest Neighbor Study** — `44444444-4444-4444-8444-000000000008`
  - Kind: `research`
  - Description: Compared HNSW and exact vector search on synthetic embeddings and documented recall-latency trade-offs.
  - Skills: HNSW, vector search, information retrieval
  - Outcome: Results were limited to the recorded synthetic benchmark.

- [x] **E9. QUIC Transport Lab** — `44444444-4444-4444-8444-000000000009`
  - Kind: `course`
  - Description: Instrumented a QUIC client to study congestion control and packet loss under emulated network conditions, capturing packet traces for reproducible scenarios.
  - Skills: QUIC, networking, congestion control
  - Outcome: Captured packet traces for reproducible scenarios.

- [x] **E10. TLA+ Specification** — `44444444-4444-4444-8444-000000000010`
  - Kind: `research`
  - Description: Specified a distributed lock in TLA+ and model-checked safety and liveness properties.
  - Skills: TLA+, formal methods, distributed systems
  - Outcome: The model checker found and reproduced an initial deadlock.

## Part B — Development queries (40)

### 1. [x] `61111111-1111-4111-8111-000000000001`

- Profile: `backend-platform`
- Purpose: Direct framework and database match.
- Requirement: **Build Python APIs with FastAPI and PostgreSQL.**
- Category / normalized skill: `must_have` / `python backend development`
- Tags: exact_skill, lexical, hard_negative
- Relevant evidence:
  - **full** — Order API (`11111111-1111-4111-8111-000000000001`)
    - Quote: “Built a Python FastAPI order service with PostgreSQL transactions”
    - Rationale: The candidate implemented the requested stack in one backend service.
- Hard negatives:
  - Query Tuning Lab (`11111111-1111-4111-8111-000000000008`): Used PostgreSQL EXPLAIN ANALYZE and composite indexes to optimize joins over application and task tables.

### 2. [x] `61111111-1111-4111-8111-000000000002`

- Profile: `backend-platform`
- Purpose: Composite reliability requirement split across two projects.
- Requirement: **Prevent duplicate writes and keep reads available when the cache fails.**
- Category / normalized skill: `responsibility` / `backend resilience`
- Tags: paraphrase, multi_relevant, composite, hard_negative
- Relevant evidence:
  - **partial** — Order API (`11111111-1111-4111-8111-000000000001`)
    - Quote: “idempotency keys to prevent duplicate orders”
    - Rationale: Supports duplicate-write prevention but not cache failure handling.
  - **partial** — Dashboard Cache (`11111111-1111-4111-8111-000000000005`)
    - Quote: “fails open to PostgreSQL when Redis is unavailable”
    - Rationale: Supports cache failure availability but not idempotent writes.
  - **partial** — Serverless Notification Worker (`11111111-1111-4111-8111-000000000007`)
    - Quote: “DynamoDB conditional writes for deduplication”
    - Rationale: Supports duplicate-write prevention but not cache failure handling.
- Hard negatives:
  - Event Processing Internship (`11111111-1111-4111-8111-000000000002`): Implemented Java Kafka consumers with retry topics and a dead-letter queue for malformed events.

### 3. [x] `61111111-1111-4111-8111-000000000003`

- Profile: `backend-platform`
- Purpose: Direct event-processing match.
- Requirement: **Develop Java consumers for Kafka-based event processing.**
- Category / normalized skill: `must_have` / `java kafka`
- Tags: exact_skill, lexical, hard_negative
- Relevant evidence:
  - **full** — Event Processing Internship (`11111111-1111-4111-8111-000000000002`)
    - Quote: “Implemented Java Kafka consumers with retry topics”
    - Rationale: Direct evidence of implementing Java Kafka consumers.
- Hard negatives:
  - Serverless Notification Worker (`11111111-1111-4111-8111-000000000007`): Processed notification jobs with AWS Lambda and SQS, using DynamoDB conditional writes for deduplication.

### 4. [x] `61111111-1111-4111-8111-000000000004`

- Profile: `backend-platform`
- Purpose: Composite deployment requirement with a serverless distractor.
- Requirement: **Ship containerized services through CI/CD with health checks and rollback procedures.**
- Category / normalized skill: `responsibility` / `container delivery`
- Tags: lexical, composite, hard_negative
- Relevant evidence:
  - **full** — Container Delivery Pipeline (`11111111-1111-4111-8111-000000000003`)
    - Quote: “Packaged a service with Docker and deployed it to Kubernetes through GitHub Actions with health checks and rollback steps”
    - Rationale: One project demonstrates the complete delivery workflow.
- Hard negatives:
  - Serverless Notification Worker (`11111111-1111-4111-8111-000000000007`): Processed notification jobs with AWS Lambda and SQS, using DynamoDB conditional writes for deduplication.

### 5. [x] `61111111-1111-4111-8111-000000000005`

- Profile: `backend-platform`
- Purpose: Direct authorization match.
- Requirement: **Implement OAuth2, JWT validation, and role-based access control.**
- Category / normalized skill: `must_have` / `api authorization`
- Tags: exact_skill, lexical, hard_negative
- Relevant evidence:
  - **full** — Authorization Service (`11111111-1111-4111-8111-000000000004`)
    - Quote: “OAuth2 login, JWT validation, and role-based authorization checks”
    - Rationale: The experience covers every named authorization mechanism.
- Hard negatives:
  - Order API (`11111111-1111-4111-8111-000000000001`): Built a Python FastAPI order service with PostgreSQL transactions and idempotency keys to prevent duplicate orders.

### 6. [x] `61111111-1111-4111-8111-000000000006`

- Profile: `backend-platform`
- Purpose: Transaction safety expressed without exact project terminology.
- Requirement: **Protect financial state from retries and simultaneous updates.**
- Category / normalized skill: `responsibility` / `transactional consistency`
- Tags: paraphrase, multi_relevant, composite, hard_negative
- Relevant evidence:
  - **partial** — Payment Ledger (`11111111-1111-4111-8111-000000000009`)
    - Quote: “serializable transactions to preserve account balances”
    - Rationale: Supports simultaneous-update safety but not retry safety.
  - **partial** — Order API (`11111111-1111-4111-8111-000000000001`)
    - Quote: “idempotency keys to prevent duplicate orders”
    - Rationale: Supports retry safety but not the financial balance invariant.
- Hard negatives:
  - Concurrent Rate Limiter (`11111111-1111-4111-8111-000000000006`): Wrote a Go token-bucket rate limiter and tested concurrent clients for race-free quota enforcement.

### 7. [x] `61111111-1111-4111-8111-000000000007`

- Profile: `backend-platform`
- Purpose: Negative for an absent web framework.
- Requirement: **Maintain production applications built with Ruby on Rails.**
- Category / normalized skill: `must_have` / `ruby on rails`
- Tags: hard_negative
- Relevant evidence: **none**
- Negative rationale: The profile has backend applications but no Ruby or Rails implementation evidence.
- Hard negatives:
  - Order API (`11111111-1111-4111-8111-000000000001`): Built a Python FastAPI order service with PostgreSQL transactions and idempotency keys to prevent duplicate orders.
  - GraphQL Catalog (`11111111-1111-4111-8111-000000000010`): Created a Node.js GraphQL catalog API and documented Rust as a possible future rewrite without implementing it.

### 8. [x] `61111111-1111-4111-8111-000000000008`

- Profile: `backend-platform`
- Purpose: Negative for infrastructure-as-code despite deployment experience.
- Requirement: **Provision cloud infrastructure with Terraform modules.**
- Category / normalized skill: `nice_to_have` / `terraform`
- Tags: hard_negative
- Relevant evidence: **none**
- Negative rationale: Deployment and AWS usage do not demonstrate Terraform or infrastructure provisioning.
- Hard negatives:
  - Container Delivery Pipeline (`11111111-1111-4111-8111-000000000003`): Packaged a service with Docker and deployed it to Kubernetes through GitHub Actions with health checks and rollback steps.
  - Serverless Notification Worker (`11111111-1111-4111-8111-000000000007`): Processed notification jobs with AWS Lambda and SQS, using DynamoDB conditional writes for deduplication.

### 9. [x] `61111111-1111-4111-8111-000000000009`

- Profile: `backend-platform`
- Purpose: Chinese requirement retrieving English AWS worker evidence.
- Requirement: **使用 AWS 无服务器组件构建可去重的异步任务处理流程。**
- Category / normalized skill: `responsibility` / `aws serverless processing`
- Tags: paraphrase, zh_en, composite, hard_negative
- Relevant evidence:
  - **full** — Serverless Notification Worker (`11111111-1111-4111-8111-000000000007`)
    - Quote: “AWS Lambda and SQS, using DynamoDB conditional writes for deduplication”
    - Rationale: The English experience covers serverless asynchronous processing and deduplication.
- Hard negatives:
  - Event Processing Internship (`11111111-1111-4111-8111-000000000002`): Implemented Java Kafka consumers with retry topics and a dead-letter queue for malformed events.

### 10. [x] `61111111-1111-4111-8111-000000000010`

- Profile: `backend-platform`
- Purpose: Negative where Rust appears only as a future idea.
- Requirement: **Operate a production backend implemented in Rust.**
- Category / normalized skill: `must_have` / `rust backend`
- Tags: hard_negative
- Relevant evidence: **none**
- Negative rationale: Rust was only documented as a possible rewrite and was not implemented or operated.
- Hard negatives:
  - GraphQL Catalog (`11111111-1111-4111-8111-000000000010`): Created a Node.js GraphQL catalog API and documented Rust as a possible future rewrite without implementing it.

### 11. [x] `62222222-2222-4222-8222-000000000001`

- Profile: `data-ai`
- Purpose: Direct warehouse pipeline match.
- Requirement: **Build Airflow pipelines that load modeled data into Snowflake.**
- Category / normalized skill: `must_have` / `airflow snowflake etl`
- Tags: exact_skill, lexical, hard_negative
- Relevant evidence:
  - **full** — Analytics Warehouse Pipeline (`22222222-2222-4222-8222-000000000001`)
    - Quote: “Airflow and modeled validated warehouse tables with dbt and Snowflake”
    - Rationale: Direct evidence of orchestrating and modeling Snowflake loads.
- Hard negatives:
  - Operations Analytics (`22222222-2222-4222-8222-000000000009`): Wrote documented SQL transformations and built Tableau dashboards whose charts were traceable to those queries.

### 12. [x] `62222222-2222-4222-8222-000000000002`

- Profile: `data-ai`
- Purpose: Semantic retrieval quality requirement.
- Requirement: **Measure whether a knowledge-grounded assistant retrieves the right evidence before generation.**
- Category / normalized skill: `responsibility` / `rag retrieval evaluation`
- Tags: paraphrase, hard_negative
- Relevant evidence:
  - **full** — Evidence Retrieval Research (`22222222-2222-4222-8222-000000000002`)
    - Quote: “retrieval-augmented generation prototype with text embeddings and labeled Recall@K evaluation cases”
    - Rationale: The project evaluates evidence retrieval for a grounded generation workflow.
- Hard negatives:
  - Image Classification Lab (`22222222-2222-4222-8222-000000000007`): Fine-tuned a TensorFlow image classifier and analyzed class-level confusion matrices.

### 13. [x] `62222222-2222-4222-8222-000000000003`

- Profile: `data-ai`
- Purpose: Direct experiment reproducibility match.
- Requirement: **Track scikit-learn experiments with MLflow and reproducible Docker jobs.**
- Category / normalized skill: `nice_to_have` / `mlops experiment tracking`
- Tags: exact_skill, lexical, hard_negative
- Relevant evidence:
  - **full** — Model Experiment Registry (`22222222-2222-4222-8222-000000000003`)
    - Quote: “Tracked scikit-learn experiments with MLflow and packaged reproducible training jobs in Docker”
    - Rationale: The exact experiment tracking and packaging workflow is demonstrated.
- Hard negatives:
  - Demand Forecasting (`22222222-2222-4222-8222-000000000006`): Trained scikit-learn time-series baselines and evaluated them with rolling temporal validation.

### 14. [x] `62222222-2222-4222-8222-000000000004`

- Profile: `data-ai`
- Purpose: Composite streaming and batch data requirement.
- Requirement: **Design both real-time event aggregation and scheduled warehouse transformations.**
- Category / normalized skill: `responsibility` / `batch and streaming data`
- Tags: paraphrase, multi_relevant, composite, hard_negative
- Relevant evidence:
  - **partial** — Streaming Feature Pipeline (`22222222-2222-4222-8222-000000000004`)
    - Quote: “Spark Structured Streaming, wrote windowed aggregates”
    - Rationale: Supports the real-time aggregation half.
  - **partial** — Analytics Warehouse Pipeline (`22222222-2222-4222-8222-000000000001`)
    - Quote: “Orchestrated daily Python ETL jobs with Airflow”
    - Rationale: Supports the scheduled transformation half.
- Hard negatives:
  - Operations Analytics (`22222222-2222-4222-8222-000000000009`): Wrote documented SQL transformations and built Tableau dashboards whose charts were traceable to those queries.

### 15. [x] `62222222-2222-4222-8222-000000000005`

- Profile: `data-ai`
- Purpose: Feature freshness match.
- Requirement: **Serve versioned ML features online and reject stale values.**
- Category / normalized skill: `responsibility` / `online feature store`
- Tags: paraphrase, hard_negative
- Relevant evidence:
  - **full** — Feature Store Prototype (`22222222-2222-4222-8222-000000000005`)
    - Quote: “Served versioned machine-learning features through Feast with Redis online storage and rejected stale features through freshness validation”
    - Rationale: The feature store includes versioned online serving and stale-value rejection.
- Hard negatives:
  - Streaming Feature Pipeline (`22222222-2222-4222-8222-000000000004`): Processed Kafka events with Spark Structured Streaming, wrote windowed aggregates to a feature table, and exercised late events with deterministic fixtures.

### 16. [x] `62222222-2222-4222-8222-000000000006`

- Profile: `data-ai`
- Purpose: Chinese requirement retrieving English forecasting evidence.
- Requirement: **使用滚动时间验证评估需求预测基线。**
- Category / normalized skill: `must_have` / `time series forecasting`
- Tags: paraphrase, zh_en, hard_negative
- Relevant evidence:
  - **full** — Demand Forecasting (`22222222-2222-4222-8222-000000000006`)
    - Quote: “Trained scikit-learn time-series baselines and evaluated them with rolling temporal validation”
    - Rationale: The English experience explicitly uses rolling temporal validation for forecasting baselines.
- Hard negatives:
  - Model Experiment Registry (`22222222-2222-4222-8222-000000000003`): Tracked scikit-learn experiments with MLflow and packaged reproducible training jobs in Docker.

### 17. [x] `62222222-2222-4222-8222-000000000007`

- Profile: `data-ai`
- Purpose: Negative for absent language-model training.
- Requirement: **Fine-tune large language models with distributed GPU training.**
- Category / normalized skill: `must_have` / `llm fine tuning`
- Tags: hard_negative
- Relevant evidence: **none**
- Negative rationale: RAG and image classification work do not demonstrate LLM fine-tuning or distributed GPU training.
- Hard negatives:
  - Evidence Retrieval Research (`22222222-2222-4222-8222-000000000002`): Built a Python retrieval-augmented generation prototype with text embeddings and labeled Recall@K evaluation cases.
  - Image Classification Lab (`22222222-2222-4222-8222-000000000007`): Fine-tuned a TensorFlow image classifier and analyzed class-level confusion matrices.

### 18. [x] `62222222-2222-4222-8222-000000000008`

- Profile: `data-ai`
- Purpose: Negative where a topic was presented but not implemented.
- Requirement: **Implement differentially private model training in production.**
- Category / normalized skill: `responsibility` / `differential privacy`
- Tags: hard_negative
- Relevant evidence: **none**
- Negative rationale: The profile only presented papers and explicitly did not implement such a system.
- Hard negatives:
  - Privacy Reading Group (`22222222-2222-4222-8222-000000000010`): Presented papers about differential privacy but did not implement a privacy-preserving training system.

### 19. [x] `62222222-2222-4222-8222-000000000009`

- Profile: `data-ai`
- Purpose: Data correctness distributed across validation projects.
- Requirement: **Block schema-invalid batches and stale online features before consumers see them.**
- Category / normalized skill: `responsibility` / `data validation`
- Tags: paraphrase, multi_relevant, composite, hard_negative
- Relevant evidence:
  - **partial** — Data Contract Monitor (`22222222-2222-4222-8222-000000000008`)
    - Quote: “checks for schema drift, missing values, and invalid categorical fields”
    - Rationale: Supports schema and batch validation.
  - **partial** — Feature Store Prototype (`22222222-2222-4222-8222-000000000005`)
    - Quote: “rejected stale features through freshness validation”
    - Rationale: Supports blocking stale online features.
- Hard negatives:
  - Analytics Warehouse Pipeline (`22222222-2222-4222-8222-000000000001`): Orchestrated daily Python ETL jobs with Airflow and modeled validated warehouse tables with dbt and Snowflake, blocking incomplete loads before table updates.

### 20. [x] `62222222-2222-4222-8222-000000000010`

- Profile: `data-ai`
- Purpose: Chinese request for an English vision experience.
- Requirement: **能够训练图像分类模型，并分析不同类别的错误模式。**
- Category / normalized skill: `nice_to_have` / `image classification`
- Tags: paraphrase, zh_en, composite, hard_negative
- Relevant evidence:
  - **full** — Image Classification Lab (`22222222-2222-4222-8222-000000000007`)
    - Quote: “Fine-tuned a TensorFlow image classifier and analyzed class-level confusion matrices”
    - Rationale: The experience demonstrates both training and class-specific error analysis.
- Hard negatives:
  - Demand Forecasting (`22222222-2222-4222-8222-000000000006`): Trained scikit-learn time-series baselines and evaluated them with rolling temporal validation.

### 21. [x] `63333333-3333-4333-8333-000000000001`

- Profile: `frontend-mobile`
- Purpose: Direct accessible React match.
- Requirement: **Build accessible React interfaces in TypeScript with keyboard support.**
- Category / normalized skill: `must_have` / `accessible react`
- Tags: exact_skill, lexical, hard_negative
- Relevant evidence:
  - **full** — Accessible React Dashboard (`33333333-3333-4333-8333-000000000001`)
    - Quote: “React and TypeScript dashboard with keyboard navigation”
    - Rationale: The experience directly covers framework, language, and accessibility behavior.
- Hard negatives:
  - Component Library (`33333333-3333-4333-8333-000000000006`): Maintained reusable TypeScript components in Storybook with design tokens and visual regression tests, documenting component states and accessibility expectations.

### 22. [x] `63333333-3333-4333-8333-000000000002`

- Profile: `frontend-mobile`
- Purpose: Server-rendered commerce match.
- Requirement: **Deliver an SEO-friendly storefront using server-side rendering and caching.**
- Category / normalized skill: `responsibility` / `nextjs ssr`
- Tags: paraphrase, composite, hard_negative
- Relevant evidence:
  - **full** — Next.js Storefront (`33333333-3333-4333-8333-000000000002`)
    - Quote: “server-side rendering, route-level caching, and structured metadata”
    - Rationale: The storefront demonstrates the complete SEO and rendering requirement.
- Hard negatives:
  - Web Performance Audit (`33333333-3333-4333-8333-000000000007`): Reduced client JavaScript through code splitting, lazy loading, and image optimization, then profiled Core Web Vitals.

### 23. [x] `63333333-3333-4333-8333-000000000003`

- Profile: `frontend-mobile`
- Purpose: Offline-first behavior phrased as field resilience.
- Requirement: **Let field users continue entering records without connectivity and reconcile changes later.**
- Category / normalized skill: `responsibility` / `offline mobile sync`
- Tags: paraphrase, hard_negative
- Relevant evidence:
  - **full** — Offline Field App (`33333333-3333-4333-8333-000000000003`)
    - Quote: “offline queue and conflict-aware synchronization after reconnection”
    - Rationale: The mobile app supports offline entry and later reconciliation.
- Hard negatives:
  - iOS Study Timer (`33333333-3333-4333-8333-000000000005`): Built a SwiftUI study timer with local notifications and persisted session history using Core Data.

### 24. [x] `63333333-3333-4333-8333-000000000004`

- Profile: `frontend-mobile`
- Purpose: Composite native mobile requirement across two platforms.
- Requirement: **Develop native mobile applications for both Android and iOS.**
- Category / normalized skill: `nice_to_have` / `native mobile development`
- Tags: paraphrase, multi_relevant, composite, hard_negative
- Relevant evidence:
  - **partial** — Android Campus Map (`33333333-3333-4333-8333-000000000004`)
    - Quote: “Kotlin Android application with Jetpack Compose”
    - Rationale: Supports Android but not iOS.
  - **partial** — iOS Study Timer (`33333333-3333-4333-8333-000000000005`)
    - Quote: “Built a SwiftUI study timer”
    - Rationale: Supports iOS but not Android.
- Hard negatives:
  - Offline Field App (`33333333-3333-4333-8333-000000000003`): Developed a React Native field app with an offline queue and conflict-aware synchronization after reconnection; recovery tests preserved locally entered records across network loss.

### 25. [x] `63333333-3333-4333-8333-000000000005`

- Profile: `frontend-mobile`
- Purpose: Direct design-system match.
- Requirement: **Maintain a TypeScript component library in Storybook with visual regression coverage.**
- Category / normalized skill: `must_have` / `design systems`
- Tags: exact_skill, lexical, hard_negative
- Relevant evidence:
  - **full** — Component Library (`33333333-3333-4333-8333-000000000006`)
    - Quote: “TypeScript components in Storybook with design tokens and visual regression tests”
    - Rationale: Direct evidence for all requested component-library practices.
- Hard negatives:
  - Accessible React Dashboard (`33333333-3333-4333-8333-000000000001`): Built a React and TypeScript dashboard with keyboard navigation, semantic HTML, and automated accessibility checks.

### 26. [x] `63333333-3333-4333-8333-000000000006`

- Profile: `frontend-mobile`
- Purpose: Negative for an unimplemented browser runtime technology.
- Requirement: **Optimize compute-heavy browser features with WebAssembly.**
- Category / normalized skill: `nice_to_have` / `webassembly`
- Tags: hard_negative
- Relevant evidence: **none**
- Negative rationale: The performance audit used web loading techniques but no WebAssembly implementation.
- Hard negatives:
  - Web Performance Audit (`33333333-3333-4333-8333-000000000007`): Reduced client JavaScript through code splitting, lazy loading, and image optimization, then profiled Core Web Vitals.

### 27. [x] `63333333-3333-4333-8333-000000000007`

- Profile: `frontend-mobile`
- Purpose: Negative for a different cross-platform framework.
- Requirement: **Ship cross-platform mobile features with Flutter and Dart.**
- Category / normalized skill: `must_have` / `flutter`
- Tags: hard_negative
- Relevant evidence: **none**
- Negative rationale: The profile has React Native, Android, and iOS work but no Flutter or Dart evidence.
- Hard negatives:
  - Offline Field App (`33333333-3333-4333-8333-000000000003`): Developed a React Native field app with an offline queue and conflict-aware synchronization after reconnection; recovery tests preserved locally entered records across network loss.
  - Android Campus Map (`33333333-3333-4333-8333-000000000004`): Created a Kotlin Android application with Jetpack Compose, location permissions, and cached map markers.
  - iOS Study Timer (`33333333-3333-4333-8333-000000000005`): Built a SwiftUI study timer with local notifications and persisted session history using Core Data.

### 28. [x] `63333333-3333-4333-8333-000000000008`

- Profile: `frontend-mobile`
- Purpose: Negative for GraphQL despite API integration experience.
- Requirement: **Implement real-time GraphQL subscriptions for the client.**
- Category / normalized skill: `nice_to_have` / `graphql subscriptions`
- Tags: hard_negative
- Relevant evidence: **none**
- Negative rationale: The backend-for-frontend demonstrates API aggregation but not GraphQL or subscriptions.
- Hard negatives:
  - Frontend Backend-for-Frontend (`33333333-3333-4333-8333-000000000009`): Implemented a Node.js Express backend-for-frontend that aggregated PostgreSQL data for a React client.
- Hard-negative rationale: This is the closest in-profile distractor because it connects a Node API to React, while still lacking GraphQL and subscriptions.

### 29. [x] `63333333-3333-4333-8333-000000000009`

- Profile: `frontend-mobile`
- Purpose: Chinese requirement retrieving English localization evidence.
- Requirement: **为中英文用户提供本地化文案、日期格式和缺失翻译回退。**
- Category / normalized skill: `responsibility` / `internationalization`
- Tags: paraphrase, zh_en, composite, hard_negative
- Relevant evidence:
  - **full** — Bilingual Interface (`33333333-3333-4333-8333-000000000010`)
    - Quote: “Localized a web interface in English and Chinese with ICU message formatting, locale-aware dates, and missing-translation fallbacks”
    - Rationale: The bilingual project covers messages, locale-aware dates, and documented fallbacks.
- Hard negatives:
  - Accessible React Dashboard (`33333333-3333-4333-8333-000000000001`): Built a React and TypeScript dashboard with keyboard navigation, semantic HTML, and automated accessibility checks.

### 30. [x] `63333333-3333-4333-8333-000000000010`

- Profile: `frontend-mobile`
- Purpose: Checkout behavior and accessibility testing across two projects.
- Requirement: **Automate checkout failure paths and verify keyboard-only interaction.**
- Category / normalized skill: `responsibility` / `browser accessibility testing`
- Tags: paraphrase, multi_relevant, composite, hard_negative
- Relevant evidence:
  - **full** — Checkout Browser Tests (`33333333-3333-4333-8333-000000000008`)
    - Quote: “Playwright end-to-end tests for checkout, failed payments, and keyboard-only navigation”
    - Rationale: One suite directly tests both requested behaviors.
  - **partial** — Accessible React Dashboard (`33333333-3333-4333-8333-000000000001`)
    - Quote: “keyboard navigation”
    - Rationale: Supports keyboard accessibility but not checkout failure testing.
- Hard negatives:
  - Component Library (`33333333-3333-4333-8333-000000000006`): Maintained reusable TypeScript components in Storybook with design tokens and visual regression tests, documenting component states and accessibility expectations.

### 31. [x] `64444444-4444-4444-8444-000000000001`

- Profile: `systems-research`
- Purpose: Multiple C++ systems experiences for storage or parser reliability.
- Requirement: **Build systems software in C++ with storage or parser experience.**
- Category / normalized skill: `must_have` / `c++ systems`
- Tags: lexical, multi_relevant, composite, hard_negative
- Relevant evidence:
  - **full** — LSM Storage Engine (`44444444-4444-4444-8444-000000000001`)
    - Quote: “C++ log-structured merge storage engine”
    - Rationale: Direct C++ storage-systems evidence.
  - **partial** — Protocol Fuzzing (`44444444-4444-4444-8444-000000000007`)
    - Quote: “coverage-guided fuzz tests in C++ for a binary protocol parser”
    - Rationale: Demonstrates C++ parser testing, but not that the candidate built the parser or broader systems software.
- Hard negatives:
  - LLVM Compiler Pass (`44444444-4444-4444-8444-000000000005`): Wrote an LLVM optimization pass in C++ and used regression tests against reference outputs to detect incorrect transformations.

### 32. [x] `64444444-4444-4444-8444-000000000002`

- Profile: `systems-research`
- Purpose: Direct Rust networking match.
- Requirement: **Develop asynchronous network services in Rust using Tokio.**
- Category / normalized skill: `must_have` / `rust async networking`
- Tags: exact_skill, lexical, hard_negative
- Relevant evidence:
  - **full** — Async Network Server (`44444444-4444-4444-8444-000000000002`)
    - Quote: “Rust asynchronous TCP server with Tokio”
    - Rationale: Direct implementation evidence for the requested stack.
- Hard negatives:
  - QUIC Transport Lab (`44444444-4444-4444-8444-000000000009`): Instrumented a QUIC client to study congestion control and packet loss under emulated network conditions, capturing packet traces for reproducible scenarios.

### 33. [x] `64444444-4444-4444-8444-000000000003`

- Profile: `systems-research`
- Purpose: Operating-systems implementation match.
- Requirement: **Hands-on operating systems work with scheduling and virtual memory.**
- Category / normalized skill: `education` / `operating systems`
- Tags: paraphrase, composite, hard_negative
- Relevant evidence:
  - **full** — Teaching Kernel (`44444444-4444-4444-8444-000000000003`)
    - Quote: “priority scheduling and copy-on-write process memory”
    - Rationale: The kernel work covers both scheduling and virtual memory.
- Hard negatives:
  - LSM Storage Engine (`44444444-4444-4444-8444-000000000001`): Implemented a C++ log-structured merge storage engine with write-ahead logging, compaction, and concurrent reads.

### 34. [x] `64444444-4444-4444-8444-000000000004`

- Profile: `systems-research`
- Purpose: Consensus behavior phrased as failure recovery.
- Requirement: **Test replicated systems under leader-loss and log-repair scenarios.**
- Category / normalized skill: `responsibility` / `distributed consensus`
- Tags: paraphrase, hard_negative
- Relevant evidence:
  - **full** — Replicated Key-Value Store (`44444444-4444-4444-8444-000000000004`)
    - Quote: “Fault-injection tests covered leader loss and log repair”
    - Rationale: The replicated key-value store was tested under both named failure scenarios.
- Hard negatives:
  - TLA+ Specification (`44444444-4444-4444-8444-000000000010`): Specified a distributed lock in TLA+ and model-checked safety and liveness properties.

### 35. [x] `64444444-4444-4444-8444-000000000005`

- Profile: `systems-research`
- Purpose: Direct compiler implementation match.
- Requirement: **Implement and validate optimization passes in LLVM.**
- Category / normalized skill: `nice_to_have` / `llvm compilers`
- Tags: exact_skill, lexical, hard_negative
- Relevant evidence:
  - **full** — LLVM Compiler Pass (`44444444-4444-4444-8444-000000000005`)
    - Quote: “Wrote an LLVM optimization pass in C++ and used regression tests against reference outputs to detect incorrect transformations”
    - Rationale: Direct compiler-pass implementation and validation evidence.
- Hard negatives:
  - LSM Storage Engine (`44444444-4444-4444-8444-000000000001`): Implemented a C++ log-structured merge storage engine with write-ahead logging, compaction, and concurrent reads.

### 36. [x] `64444444-4444-4444-8444-000000000006`

- Profile: `systems-research`
- Purpose: Direct GPU optimization match.
- Requirement: **Optimize CUDA kernels through memory-access and occupancy profiling.**
- Category / normalized skill: `must_have` / `cuda optimization`
- Tags: exact_skill, lexical, hard_negative
- Relevant evidence:
  - **full** — CUDA Matrix Kernels (`44444444-4444-4444-8444-000000000006`)
    - Quote: “shared memory, coalesced access, and occupancy profiling”
    - Rationale: The research work demonstrates every requested optimization technique.
- Hard negatives:
  - Approximate Nearest Neighbor Study (`44444444-4444-4444-8444-000000000008`): Compared HNSW and exact vector search on synthetic embeddings and documented recall-latency trade-offs.

### 37. [x] `64444444-4444-4444-8444-000000000007`

- Profile: `systems-research`
- Purpose: Negative for orchestration despite distributed-systems work.
- Requirement: **Operate Kubernetes clusters and write Helm charts.**
- Category / normalized skill: `must_have` / `kubernetes`
- Tags: hard_negative
- Relevant evidence: **none**
- Negative rationale: Distributed systems experience does not demonstrate Kubernetes operations or Helm.
- Hard negatives:
  - Replicated Key-Value Store (`44444444-4444-4444-8444-000000000004`): Implemented Raft leader election and log replication in Go for a replicated key-value store.
  - TLA+ Specification (`44444444-4444-4444-8444-000000000010`): Specified a distributed lock in TLA+ and model-checked safety and liveness properties.

### 38. [x] `64444444-4444-4444-8444-000000000008`

- Profile: `systems-research`
- Purpose: Negative for enterprise Java services.
- Requirement: **Build Spring Boot microservices in Java.**
- Category / normalized skill: `must_have` / `java spring boot`
- Tags: hard_negative
- Relevant evidence: **none**
- Negative rationale: The profile has networked and distributed services but no Java or Spring Boot evidence.
- Hard negatives:
  - Async Network Server (`44444444-4444-4444-8444-000000000002`): Built a Rust asynchronous TCP server with Tokio, bounded queues, and graceful shutdown.
  - Replicated Key-Value Store (`44444444-4444-4444-8444-000000000004`): Implemented Raft leader election and log replication in Go for a replicated key-value store.

### 39. [x] `64444444-4444-4444-8444-000000000009`

- Profile: `systems-research`
- Purpose: Chinese requirement retrieving English vector-search evidence.
- Requirement: **比较近似向量索引与精确搜索，并解释召回率和延迟之间的权衡。**
- Category / normalized skill: `responsibility` / `vector retrieval evaluation`
- Tags: paraphrase, zh_en, composite, hard_negative
- Relevant evidence:
  - **full** — Approximate Nearest Neighbor Study (`44444444-4444-4444-8444-000000000008`)
    - Quote: “Compared HNSW and exact vector search on synthetic embeddings and documented recall-latency trade-offs”
    - Rationale: The English research experience exactly matches the Chinese requirement.
- Hard negatives:
  - CUDA Matrix Kernels (`44444444-4444-4444-8444-000000000006`): Optimized CUDA matrix kernels using shared memory, coalesced access, and occupancy profiling.

### 40. [x] `64444444-4444-4444-8444-000000000010`

- Profile: `systems-research`
- Purpose: Implementation and specification evidence for distributed correctness.
- Requirement: **Reason about distributed-system safety using both implementation tests and formal specifications.**
- Category / normalized skill: `nice_to_have` / `distributed systems correctness`
- Tags: paraphrase, multi_relevant, composite, hard_negative
- Relevant evidence:
  - **partial** — TLA+ Specification (`44444444-4444-4444-8444-000000000010`)
    - Quote: “model-checked safety and liveness properties”
    - Rationale: Supports formal specification and verification.
  - **partial** — Replicated Key-Value Store (`44444444-4444-4444-8444-000000000004`)
    - Quote: “Fault-injection tests covered leader loss and log repair”
    - Rationale: Supports implementation-level failure testing.
- Hard negatives:
  - LSM Storage Engine (`44444444-4444-4444-8444-000000000001`): Implemented a C++ log-structured merge storage engine with write-ahead logging, compaction, and concurrent reads.

## Part C — Frozen holdout labels (20)

### 1. [x] `81111111-1111-4111-8111-000000000001`

- Profile: `backend-platform`
- Purpose: Database performance evidence without naming the course title.
- Requirement: **Diagnose slow relational queries and design appropriate indexes.**
- Category / normalized skill: `responsibility` / `sql performance`
- Tags: paraphrase, hard_negative
- Relevant evidence:
  - **full** — Query Tuning Lab (`11111111-1111-4111-8111-000000000008`)
    - Quote: “PostgreSQL EXPLAIN ANALYZE and composite indexes to optimize joins”
    - Rationale: The lab demonstrates query diagnosis and index design.
- Hard negatives:
  - Order API (`11111111-1111-4111-8111-000000000001`): Built a Python FastAPI order service with PostgreSQL transactions and idempotency keys to prevent duplicate orders.

### 2. [x] `81111111-1111-4111-8111-000000000002`

- Profile: `backend-platform`
- Purpose: Concurrency control match in Go.
- Requirement: **Write race-free concurrent services in Go.**
- Category / normalized skill: `must_have` / `go concurrency`
- Tags: exact_skill, hard_negative
- Relevant evidence:
  - **full** — Concurrent Rate Limiter (`11111111-1111-4111-8111-000000000006`)
    - Quote: “Wrote a Go token-bucket rate limiter and tested concurrent clients for race-free quota enforcement”
    - Rationale: The implementation and race checks directly support the requirement.
- Hard negatives:
  - Payment Ledger (`11111111-1111-4111-8111-000000000009`): Designed a payment ledger with database unique constraints and serializable transactions to preserve account balances.

### 3. [x] `81111111-1111-4111-8111-000000000003`

- Profile: `backend-platform`
- Purpose: Reliable asynchronous delivery across broker and serverless projects.
- Requirement: **Make asynchronous jobs recoverable from malformed messages and duplicate delivery.**
- Category / normalized skill: `responsibility` / `reliable async processing`
- Tags: paraphrase, multi_relevant, composite, hard_negative
- Relevant evidence:
  - **partial** — Event Processing Internship (`11111111-1111-4111-8111-000000000002`)
    - Quote: “retry topics and a dead-letter queue for malformed events”
    - Rationale: Supports malformed-message recovery.
  - **partial** — Serverless Notification Worker (`11111111-1111-4111-8111-000000000007`)
    - Quote: “DynamoDB conditional writes for deduplication”
    - Rationale: Supports duplicate-delivery protection.
- Hard negatives:
  - Order API (`11111111-1111-4111-8111-000000000001`): Built a Python FastAPI order service with PostgreSQL transactions and idempotency keys to prevent duplicate orders.
- Hard-negative rationale: The Order API's idempotency handles synchronous request retries, not duplicate delivery of asynchronous messages or jobs.

### 4. [x] `81111111-1111-4111-8111-000000000004`

- Profile: `backend-platform`
- Purpose: Negative for an RPC stack not used by the rate limiter.
- Requirement: **Design gRPC APIs and Protocol Buffers schemas.**
- Category / normalized skill: `must_have` / `grpc protobuf`
- Tags: hard_negative
- Relevant evidence: **none**
- Negative rationale: Go and API work do not establish gRPC or Protocol Buffers experience.
- Hard negatives:
  - Concurrent Rate Limiter (`11111111-1111-4111-8111-000000000006`): Wrote a Go token-bucket rate limiter and tested concurrent clients for race-free quota enforcement.
  - GraphQL Catalog (`11111111-1111-4111-8111-000000000010`): Created a Node.js GraphQL catalog API and documented Rust as a possible future rewrite without implementing it.

### 5. [x] `81111111-1111-4111-8111-000000000005`

- Profile: `backend-platform`
- Purpose: Negative for a document database.
- Requirement: **Model and operate high-volume collections in MongoDB.**
- Category / normalized skill: `nice_to_have` / `mongodb`
- Tags: hard_negative
- Relevant evidence: **none**
- Negative rationale: The profile uses PostgreSQL, Redis, and DynamoDB but provides no MongoDB evidence.
- Hard negatives:
  - Dashboard Cache (`11111111-1111-4111-8111-000000000005`): Implemented a Redis cache that fails open to PostgreSQL when Redis is unavailable or returns malformed JSON.
  - Query Tuning Lab (`11111111-1111-4111-8111-000000000008`): Used PostgreSQL EXPLAIN ANALYZE and composite indexes to optimize joins over application and task tables.

### 6. [x] `82222222-2222-4222-8222-000000000001`

- Profile: `data-ai`
- Purpose: Dashboard traceability match.
- Requirement: **Create stakeholder dashboards whose metrics are traceable to SQL transformations.**
- Category / normalized skill: `responsibility` / `analytics dashboards`
- Tags: paraphrase, hard_negative
- Relevant evidence:
  - **full** — Operations Analytics (`22222222-2222-4222-8222-000000000009`)
    - Quote: “Wrote documented SQL transformations and built Tableau dashboards whose charts were traceable to those queries”
    - Rationale: The analytics work directly demonstrates SQL-to-chart traceability.
- Hard negatives:
  - Analytics Warehouse Pipeline (`22222222-2222-4222-8222-000000000001`): Orchestrated daily Python ETL jobs with Airflow and modeled validated warehouse tables with dbt and Snowflake, blocking incomplete loads before table updates.

### 7. [x] `82222222-2222-4222-8222-000000000002`

- Profile: `data-ai`
- Purpose: Chinese requirement retrieving English batch-pipeline evidence.
- Requirement: **编排每日批处理任务，并在数据不完整时阻止仓库表更新。**
- Category / normalized skill: `must_have` / `batch data orchestration`
- Tags: paraphrase, zh_en, composite, hard_negative
- Relevant evidence:
  - **full** — Analytics Warehouse Pipeline (`22222222-2222-4222-8222-000000000001`)
    - Quote: “Orchestrated daily Python ETL jobs with Airflow and modeled validated warehouse tables with dbt and Snowflake, blocking incomplete loads before table updates”
    - Rationale: The project combines daily orchestration with blocking incomplete warehouse loads.
- Hard negatives:
  - Streaming Feature Pipeline (`22222222-2222-4222-8222-000000000004`): Processed Kafka events with Spark Structured Streaming, wrote windowed aggregates to a feature table, and exercised late events with deterministic fixtures.

### 8. [x] `82222222-2222-4222-8222-000000000003`

- Profile: `data-ai`
- Purpose: Model reproducibility and leakage prevention split across projects.
- Requirement: **Make training reproducible and evaluate temporal models without future-data leakage.**
- Category / normalized skill: `responsibility` / `reproducible machine learning`
- Tags: paraphrase, multi_relevant, composite, hard_negative
- Relevant evidence:
  - **partial** — Model Experiment Registry (`22222222-2222-4222-8222-000000000003`)
    - Quote: “packaged reproducible training jobs in Docker”
    - Rationale: Supports reproducible training environments.
  - **partial** — Demand Forecasting (`22222222-2222-4222-8222-000000000006`)
    - Quote: “Compared models without leaking future observations”
    - Rationale: Supports leakage-safe temporal evaluation.
- Hard negatives:
  - Image Classification Lab (`22222222-2222-4222-8222-000000000007`): Fine-tuned a TensorFlow image classifier and analyzed class-level confusion matrices.

### 9. [x] `82222222-2222-4222-8222-000000000004`

- Profile: `data-ai`
- Purpose: Late-event streaming behavior.
- Requirement: **Test late-event behavior in a windowed event-processing pipeline.**
- Category / normalized skill: `nice_to_have` / `stream processing`
- Tags: paraphrase, hard_negative
- Relevant evidence:
  - **full** — Streaming Feature Pipeline (`22222222-2222-4222-8222-000000000004`)
    - Quote: “Processed Kafka events with Spark Structured Streaming, wrote windowed aggregates to a feature table, and exercised late events with deterministic fixtures”
    - Rationale: The quote establishes both the windowed streaming pipeline and its late-event tests.
- Hard negatives:
  - Analytics Warehouse Pipeline (`22222222-2222-4222-8222-000000000001`): Orchestrated daily Python ETL jobs with Airflow and modeled validated warehouse tables with dbt and Snowflake, blocking incomplete loads before table updates.

### 10. [x] `82222222-2222-4222-8222-000000000005`

- Profile: `data-ai`
- Purpose: Negative for an absent learning paradigm.
- Requirement: **Train reinforcement-learning agents for continuous-control tasks.**
- Category / normalized skill: `nice_to_have` / `reinforcement learning`
- Tags: hard_negative
- Relevant evidence: **none**
- Negative rationale: Forecasting and classification experience do not demonstrate reinforcement learning.
- Hard negatives:
  - Demand Forecasting (`22222222-2222-4222-8222-000000000006`): Trained scikit-learn time-series baselines and evaluated them with rolling temporal validation.
  - Image Classification Lab (`22222222-2222-4222-8222-000000000007`): Fine-tuned a TensorFlow image classifier and analyzed class-level confusion matrices.

### 11. [x] `83333333-3333-4333-8333-000000000001`

- Profile: `frontend-mobile`
- Purpose: Chinese accessibility requirement retrieving English evidence.
- Requirement: **构建支持键盘操作和语义化 HTML 的前端页面。**
- Category / normalized skill: `must_have` / `web accessibility`
- Tags: paraphrase, zh_en, multi_relevant, composite, hard_negative
- Relevant evidence:
  - **full** — Accessible React Dashboard (`33333333-3333-4333-8333-000000000001`)
    - Quote: “keyboard navigation, semantic HTML, and automated accessibility checks”
    - Rationale: The English project contains all requested accessibility practices.
  - **partial** — Checkout Browser Tests (`33333333-3333-4333-8333-000000000008`)
    - Quote: “keyboard-only navigation”
    - Rationale: Supports keyboard operation but not semantic HTML.
- Hard negatives:
  - Component Library (`33333333-3333-4333-8333-000000000006`): Maintained reusable TypeScript components in Storybook with design tokens and visual regression tests, documenting component states and accessibility expectations.

### 12. [x] `83333333-3333-4333-8333-000000000002`

- Profile: `frontend-mobile`
- Purpose: Mobile resilience across offline and persisted-state work.
- Requirement: **Preserve user work across network loss and application restarts on mobile devices.**
- Category / normalized skill: `responsibility` / `mobile resilience`
- Tags: paraphrase, multi_relevant, composite, hard_negative
- Relevant evidence:
  - **partial** — Offline Field App (`33333333-3333-4333-8333-000000000003`)
    - Quote: “offline queue and conflict-aware synchronization after reconnection; recovery tests preserved locally entered records across network loss”
    - Rationale: Supports preserving work through network loss, but not application restarts.
  - **partial** — iOS Study Timer (`33333333-3333-4333-8333-000000000005`)
    - Quote: “Timer state survived application restarts”
    - Rationale: Supports preserving state through application restarts.
- Hard negatives:
  - Android Campus Map (`33333333-3333-4333-8333-000000000004`): Created a Kotlin Android application with Jetpack Compose, location permissions, and cached map markers.

### 13. [x] `83333333-3333-4333-8333-000000000003`

- Profile: `frontend-mobile`
- Purpose: Backend-for-frontend integration match.
- Requirement: **Create a Node service that shapes database data for a React application.**
- Category / normalized skill: `nice_to_have` / `backend for frontend`
- Tags: paraphrase, hard_negative
- Relevant evidence:
  - **full** — Frontend Backend-for-Frontend (`33333333-3333-4333-8333-000000000009`)
    - Quote: “Node.js Express backend-for-frontend that aggregated PostgreSQL data for a React client”
    - Rationale: Direct evidence of the requested integration pattern.
- Hard negatives:
  - Next.js Storefront (`33333333-3333-4333-8333-000000000002`): Implemented a Next.js storefront with server-side rendering, route-level caching, and structured metadata.

### 14. [x] `83333333-3333-4333-8333-000000000004`

- Profile: `frontend-mobile`
- Purpose: Accessibility and reusable component evidence across projects.
- Requirement: **Define reusable UI components and document their accessibility expectations.**
- Category / normalized skill: `responsibility` / `accessible design systems`
- Tags: paraphrase, composite, hard_negative
- Relevant evidence:
  - **full** — Component Library (`33333333-3333-4333-8333-000000000006`)
    - Quote: “Maintained reusable TypeScript components in Storybook with design tokens and visual regression tests, documenting component states and accessibility expectations”
    - Rationale: The component library establishes reusable components and their accessibility expectations.
- Hard negatives:
  - Accessible React Dashboard (`33333333-3333-4333-8333-000000000001`): Built a React and TypeScript dashboard with keyboard navigation, semantic HTML, and automated accessibility checks.
  - Checkout Browser Tests (`33333333-3333-4333-8333-000000000008`): Wrote Playwright end-to-end tests for checkout, failed payments, and keyboard-only navigation.

### 15. [x] `83333333-3333-4333-8333-000000000005`

- Profile: `frontend-mobile`
- Purpose: Negative for an absent frontend framework.
- Requirement: **Maintain a Vue 3 application using Pinia.**
- Category / normalized skill: `must_have` / `vue`
- Tags: hard_negative
- Relevant evidence: **none**
- Negative rationale: React and Next.js experience do not demonstrate Vue or Pinia.
- Hard negatives:
  - Accessible React Dashboard (`33333333-3333-4333-8333-000000000001`): Built a React and TypeScript dashboard with keyboard navigation, semantic HTML, and automated accessibility checks.
  - Next.js Storefront (`33333333-3333-4333-8333-000000000002`): Implemented a Next.js storefront with server-side rendering, route-level caching, and structured metadata.

### 16. [x] `84444444-4444-4444-8444-000000000001`

- Profile: `systems-research`
- Purpose: Crash-safe local persistence requirement.
- Requirement: **Recover committed records after a storage-process crash.**
- Category / normalized skill: `responsibility` / `storage recovery`
- Tags: paraphrase, hard_negative
- Relevant evidence:
  - **full** — LSM Storage Engine (`44444444-4444-4444-8444-000000000001`)
    - Quote: “Crash-recovery tests restored committed records”
    - Rationale: The storage engine explicitly verifies the required crash recovery.
- Hard negatives:
  - Replicated Key-Value Store (`44444444-4444-4444-8444-000000000004`): Implemented Raft leader election and log replication in Go for a replicated key-value store.

### 17. [x] `84444444-4444-4444-8444-000000000002`

- Profile: `systems-research`
- Purpose: C++ correctness evidence across storage, compiler, and parser projects.
- Requirement: **Use C++ to build low-level components with regression-tested failure behavior.**
- Category / normalized skill: `must_have` / `c++ systems testing`
- Tags: paraphrase, multi_relevant, composite, hard_negative
- Relevant evidence:
  - **partial** — LSM Storage Engine (`44444444-4444-4444-8444-000000000001`)
    - Quote: “C++ log-structured merge storage engine”
    - Rationale: Supports the low-level C++ component clause, but the quote does not establish regression-tested failure behavior.
  - **full** — LLVM Compiler Pass (`44444444-4444-4444-8444-000000000005`)
    - Quote: “Wrote an LLVM optimization pass in C++ and used regression tests against reference outputs to detect incorrect transformations”
    - Rationale: The quote establishes a low-level C++ compiler component and regression tests for incorrect transformation behavior.
  - **partial** — Protocol Fuzzing (`44444444-4444-4444-8444-000000000007`)
    - Quote: “Created coverage-guided fuzz tests in C++ for a binary protocol parser, minimized crashing inputs, and added regression fixtures for every minimized crash”
    - Rationale: Supports regression-tested parser failure behavior in C++, but not that the candidate built the parser component itself.
- Hard negatives:
  - Teaching Kernel (`44444444-4444-4444-8444-000000000003`): Modified a C teaching kernel to implement priority scheduling and copy-on-write process memory.

### 18. [x] `84444444-4444-4444-8444-000000000003`

- Profile: `systems-research`
- Purpose: Chinese requirement retrieving English transport evidence.
- Requirement: **分析网络丢包条件下的拥塞控制行为，并保存可复现的数据包轨迹。**
- Category / normalized skill: `nice_to_have` / `network congestion analysis`
- Tags: paraphrase, zh_en, composite, hard_negative
- Relevant evidence:
  - **full** — QUIC Transport Lab (`44444444-4444-4444-8444-000000000009`)
    - Quote: “study congestion control and packet loss under emulated network conditions, capturing packet traces for reproducible scenarios”
    - Rationale: The transport lab covers loss, congestion control, and saved traces.
- Hard negatives:
  - Async Network Server (`44444444-4444-4444-8444-000000000002`): Built a Rust asynchronous TCP server with Tokio, bounded queues, and graceful shutdown.

### 19. [x] `84444444-4444-4444-8444-000000000004`

- Profile: `systems-research`
- Purpose: Approximate retrieval trade-off match.
- Requirement: **Evaluate when an approximate nearest-neighbor index is worth reduced retrieval completeness.**
- Category / normalized skill: `responsibility` / `approximate nearest neighbor`
- Tags: paraphrase, hard_negative
- Relevant evidence:
  - **full** — Approximate Nearest Neighbor Study (`44444444-4444-4444-8444-000000000008`)
    - Quote: “Compared HNSW and exact vector search on synthetic embeddings and documented recall-latency trade-offs”
    - Rationale: The quote compares approximate and exact search using the requested trade-off.
- Hard negatives:
  - CUDA Matrix Kernels (`44444444-4444-4444-8444-000000000006`): Optimized CUDA matrix kernels using shared memory, coalesced access, and occupancy profiling.

### 20. [x] `84444444-4444-4444-8444-000000000005`

- Profile: `systems-research`
- Purpose: Negative for hardware-description and FPGA work.
- Requirement: **Design FPGA accelerators in Verilog.**
- Category / normalized skill: `nice_to_have` / `fpga verilog`
- Tags: hard_negative
- Relevant evidence: **none**
- Negative rationale: CUDA GPU optimization does not demonstrate FPGA or Verilog development.
- Hard negatives:
  - CUDA Matrix Kernels (`44444444-4444-4444-8444-000000000006`): Optimized CUDA matrix kernels using shared memory, coalesced access, and occupancy profiling.

## Final approval

- [x] I reviewed all 40 Experiences.
- [x] I reviewed all 40 development queries.
- [x] I reviewed all 20 holdout queries without seeing retrieval rankings.
- [x] I approve freezing these labels and hashes.
