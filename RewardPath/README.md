# RewardPath

A local evidence-first opportunity planner: evaluate legitimate rewards by eligibility, obligations, costs and compatibility, then distinguish a promised reward from one actually received.

## Status
Local prototype for the Amazon Build, Ship, Shape Alexa+ track. It has not been entered, accepted, awarded or paid. Development uses AI assistance. The web interface is a deterministic assistant simulator, not a live Alexa integration or an LLM. Real MCP tool calls connect it to a local Python server.

## Run
Python 3.12 with the installed dependencies listed in requirements.txt:

    REWARDPATH_PORT=8765 python -m uvicorn server:app --host 127.0.0.1 --port 8765

Open http://127.0.0.1:8765. Persistent SQLite data defaults to .data/rewardpath.sqlite3. Set REWARDPATH_DB to an isolated path for tests or demos. No API key, AWS account, hosting, microphone, personal account or paid service is needed.

For a dependency-free local run, use `python server_stdlib.py`. It serves the same domain tools with the same MCP protocol; no package installation is needed. The SDK-backed server remains available above.

## What works
- MCP 2025-11-25 Streamable HTTP initialize, initialized notification, tools/list and tools/call.
- Bounded eligibility evaluation with pass/fail/unknown rather than guessed facts.
- Combined upfront-budget checks, incompatible-offer groups and prerequisite checks.
- Persistent ordered preparation/submission checklists with evidence requirements.
- Separate records for awards, unverified receipts, synthetic examples and real opportunities.
- Exact integer cents, duplicate receipt prevention and atomic balance checks.
- Visible real network trace and local-only host/origin protection.

## Honest limits
This is a curated-catalog prototype, not a web crawler or a legal eligibility certification. Most opportunities are explicitly fictional test cases. The separately labeled Amazon event must be rechecked against current official rules before participation. No tool enrolls, redeems, spends, publishes, transfers funds or verifies bank activity. All self-entered receipts remain unverified. Verified cash remains zero until an independent verification capability exists. A demo is not evidence of real earnings.

The UI recognizes a small number of deterministic intents, disclosed in the interface. It does not claim unconstrained conversational understanding. Tax liabilities, unknown winning probabilities and cash conversion are not fabricated.

## Tests
    python run_tests.py

Independent acceptance tests live separately in the working evaluation package. Initial review found two issues (combined budget and unconfirmed local legal majority); both were repaired and the 25-case domain suite subsequently passed. The 10-case independent HTTP protocol suite also passed. The dependency-free server was subsequently exercised in the cloud browser: filtering, incompatible-stack rejection, plan creation, ordered evidence, award/receipt separation, duplicate rejection and reload persistence. The source includes the reproducible domain and HTTP test suites.

## Data and publication
No private user data is included. Keep .data and any temporary test state out of a public repository. The source in this RewardPath directory is published under the MIT License; see LICENSE. Contest submission, eligibility verification and any prize decision are separate from source publication. All source here is newly generated for this project; dependency licenses remain applicable. The factual catalog provides source URLs; synthetic offers must never be promoted as redeemable.

## Repository layout
This RewardPath directory on the rewardpath-entry branch is the standalone RewardPath project. The repository's existing root README and main branch are unchanged. The license in this directory applies to this project only.
