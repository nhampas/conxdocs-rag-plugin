---
name: conxdocs-rag
description: "Use when working with ConXTFW test framework: asking about documentation, generating pytest test code, converting Robot Framework tests, finding fixture APIs, or understanding mandatory markers. Triggers: ConXTFW, core_ssh, core_power, GNSS test, fixture, Robot Framework conversion, test generation, pytest markers, ConX."
argument-hint: "question or task: e.g. 'How do I use core_ssh?' or '/generate reboot test' or '/convert <robot content>'"
---

# ConXDocs RAG — ConXTFW Documentation & Test Generation

Provides access to ConX Test Framework documentation via a RAG server (Retrieval-Augmented Generation). Can answer questions, generate test code, and convert Robot Framework tests.

**RAG server:** `http://10.41.80.199:8504`

Override with env var: `CONXDOCS_SERVER=http://<host>:8504`

---

## Three modes

| Mode | Command | Description |
|------|---------|-------------|
| Documentation query | (default) | Search and answer questions about ConXTFW |
| Generate test | `/generate` | Generate validated pytest code |
| Convert Robot | `/convert` | Convert `.robot` files to pytest |

### When to use which mode

| Situation | Mode |
|-----------|------|
| User asks *how* to use a fixture, marker, or pattern | `query` |
| User describes a test in plain text ("test that reboots ECU1") | `generate` |
| User provides or pastes `.robot` file content | `convert` |
| User asks to convert an existing robot test | `convert` |
| User asks what fixtures are available | `query` |

---

## When MCP or the VS Code extension is available

Use the `@rag-conxdocs` extension directly in Copilot Chat:

```
@rag-conxdocs How do I use core_ssh?
@rag-conxdocs /generate Test that reboots ECU1 and verifies SSH connection
@rag-conxdocs /convert <robot content>
```

Or let Copilot invoke the LM tools automatically:
- `conxdocs_search` — searches the documentation
- `conxdocs_generate` — generates test code
- `conxdocs_convert` — converts Robot Framework content

---

## When MCP is NOT available — Python script (fallback)

Run [query_rag.py](./scripts/query_rag.py) from the terminal or let the agent invoke it.

### Syntax

```bash
# Documentation query
python .github/skills/conxdocs-rag/scripts/query_rag.py --mode query --question "How do I use core_ssh?"

# Generate test
python .github/skills/conxdocs-rag/scripts/query_rag.py --mode generate --description "Test that reboots ECU1"

# Convert Robot file (with optional resource files)
python .github/skills/conxdocs-rag/scripts/query_rag.py --mode convert --robot-file path/to/test.robot
python .github/skills/conxdocs-rag/scripts/query_rag.py --mode convert --robot-file path/to/test.robot --resource-file common/common_vars.resource
python .github/skills/conxdocs-rag/scripts/query_rag.py --mode convert --robot-file path/to/test.robot --resource-file res1.resource --resource-file res2.resource
```

### Arguments

| Argument | Values | Description |
|----------|--------|-------------|
| `--mode` | `query`, `generate`, `convert` | Which API mode to use |
| `--question` | string | Question for the documentation RAG (mode=query) |
| `--description` | string | Description of the test to generate (mode=generate) |
| `--type` | `power`, `ssh`, `gnss`, `general` | Test type for generation (optional, auto-detected) |
| `--robot-file` | file path | Path to a `.robot` file (mode=convert) |
| `--robot-content` | string | Robot Framework content as inline string (mode=convert) |
| `--resource-file` | file path | Path to a `.resource`/`.robot` resource file. Can be repeated for multiple files. |
| `--server` | URL | Override server URL (default: http://10.41.80.199:8504) |

---

## Procedure — Documentation query

1. Identify what the user is asking about (fixture, marker, pattern, etc.)
2. Run the script in `query` mode OR use `@rag-conxdocs` / `conxdocs_search`
3. Present the answer with source references
4. If the answer is incomplete, ask a more specific follow-up question

## Procedure — Generate test code

1. Determine test type (`power`, `ssh`, `gnss`, `general`)
2. Write a clear description of what the test should do
3. Run in `generate` mode
4. Verify all `conxtfw_checks` are ✓:
   - `has_mandatory_markers` — validates that the 6 standard markers are present: `owner`, `test_scope`, `variant`, `project`, `type_designation`, `build_type`
   - `follows_aaa_pattern` — Arrange / Act / Assert
   - `has_docstring` — module-level docstring or file header comment present
5. For any ⚠️ warnings: fix the code before presenting it to the user. Note: some repos/suites (e.g. diagnostics tests) use a different marker set or no module docstring — align with the existing pattern in that repo rather than blindly adding missing markers.

## Procedure — Convert Robot Framework

1. Read a `.robot` file OR receive Robot content as text
2. Check if the file has `Resource` imports — if so, locate and include those files via `--resource-file` (variables from resource files are needed for correct conversion)
3. Run in `convert` mode
4. Verify all test cases were converted (`robot_metadata.test_cases`)
5. Check that ECU variables (`${ECU1_IP}` etc.) are correctly mapped to fixtures
6. Validate `has_mandatory_markers` and correct if missing
7. **Repo-specific adaptation (always required):** The RAG generates idiomatic ConXTFW patterns from its training data. After converting, always verify and adapt:
   - **Markers**: Check existing files in the repo's test suite. Some suites (e.g. diagnostics) use a `pytestmark` list with suite-specific markers (e.g. `swdl_level`) and no `req_id`/`doors_id`. Do not add markers that aren't already present in the target suite.
   - **Data access patterns**: Dict keys and indirection patterns (e.g. `ecu_addresses[ecu]` vs direct ECU name keys) differ per suite — check reference tests before assuming.
   - **Repo-specific helpers**: Utilities like `diagnostic_regex`, `utils.generate_ecu_params`, or `pytestmark` patterns defined in `conftest.py` will not be known to the RAG. Identify and use them where they exist.
   - **File header style**: Some suites use `# <SuiteTag>` comments rather than a module docstring. Match the existing style.

---

## Mandatory markers in ConXTFW (important!)

All tests MUST include these 6 markers as a **module-level `pytestmark` list** at the top of the file (after imports). This applies them to all test functions in the file without repetition. Do NOT put markers on individual functions or classes.

```python
import pytest

pytestmark = [
    pytest.mark.owner("<team>"),
    pytest.mark.test_scope("<scope>"),       # e.g. pre_merge_feedback, post_merge_sanity
    pytest.mark.variant("<variant>"),        # e.g. eu, china
    pytest.mark.project("<project>"),        # e.g. p519, v436
    pytest.mark.type_designation("<type>"),  # e.g. 100, 110, 200
    pytest.mark.build_type("<build>"),       # e.g. integration, unit, system
]


def test_something(core_ssh):
    ...


def test_another(core_power):
    ...
```

Common fixture categories:
- `core_ssh` — SSH communication with ECU
- `core_power` — power control (sleep, reboot, wake)
- `core_gnss` — GNSS/GPS positioning
- `core_serial` — serial communication / AT commands

---

## Troubleshooting

| Problem | Action |
|---------|--------|
| `Connection refused` | Verify the RAG server is running: `curl http://10.41.80.199:8504/health` |
| `Server returned 500` | Check server logs; the question may be too vague |
| `Syntax error` in generated code | The script returns the error message — fix and re-run |
| Empty response | Rephrase the question using more specific ConXTFW terms |
