# Upstream retry policy

## Scope

The CORTEX RAG application owns retry decisions for OpenAI embedding and chat-completion calls. The OpenAI SDK internal retry count is set to zero to prevent multiplicative retries and to make retry telemetry explicit.

## Classification

Transient failures eligible for retry:
- Network connection errors and request timeouts.
- Rate-limit responses (HTTP 429).
- HTTP 408 and 409 responses.
- HTTP 5xx responses.

Other API errors are treated as permanent and propagated immediately. The original exception is preserved when retries are exhausted.

## Backoff

The delay uses exponential growth with full jitter:

`delay = uniform(0, min(max_delay, base_delay * 2^retry_index))`

The initial call is not counted as a retry. OPENAI_MAX_RETRIES=2 therefore permits at most three total calls. The maximum delay is bounded by OPENAI_RETRY_MAX_DELAY_SECONDS.

## Configuration

- OPENAI_MAX_RETRIES: additional attempts, integer from 0 to 5.
- OPENAI_RETRY_BASE_DELAY_SECONDS: initial backoff ceiling.
- OPENAI_RETRY_MAX_DELAY_SECONDS: maximum backoff ceiling.
- OPENAI_TIMEOUT_SECONDS: timeout for each upstream request.

## Telemetry

The process-local /metrics payload exposes retry attempts, recovered operations, exhausted operations, and permanent failures. Structured logs include operation name, attempt number, and selected delay. These counters are process-local and are not a substitute for distributed telemetry.

## Validation

Automated tests use deterministic sleep and jitter substitutions to verify recovery, permanent-error short-circuiting, and maximum-attempt enforcement. No external OpenAI request is made by the tests.
