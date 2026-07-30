# Reproduction

## Environment

The audited run used:

- CPython 3.12.13;
- `pdfplumber==0.11.8`;
- `pdfminer.six==20251107`;
- Linux x86-64.

Install the pinned extraction dependencies:

```bash
python3 -m pip install -r requirements.txt
```

## Retrieve the primary source

Download:

<https://www.dmgordon.org/papers/c-12-6-3.pdf>

Require:

```text
6da3d15935e5eb8eca9e533c60ffb08db48cb335a94f88c007bd449729f8cf79  c-12-6-3.pdf
```

## Run the audit

From the release root:

```bash
bash scripts/run_audit.sh /path/to/c-12-6-3.pdf
```

The command regenerates the paper-template extraction, exact template
comparison, classification-provenance audit, and 68-entry class map under
`build/`.

Require:

- paper-template comparison: `PASS`;
- provenance checks: 18/18;
- overall provenance status: `PASS`.

The generated JSON is canonical compact JSON with sorted keys and one trailing
newline.
