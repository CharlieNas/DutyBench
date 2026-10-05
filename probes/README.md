# DutyBench probes

A quick study to see whether current models fail more often on UK lettings (Renters' Rights Act) or UK consumer lending (FCA). There are 20 cases, 2 conditions (`baseline`, `grounded`), 3 models and 3 runs each. Grading is done by hand in Excel.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install anthropic openai google-genai openpyxl pyyaml python-dotenv
```

Create `.env` in this folder (it is gitignored):

```
ANTHROPIC_API_KEY=...
OPENAI_API_KEY=...
GEMINI_API_KEY=...
```

## Run

```bash
.venv/bin/python run_probes.py --dry-run    # call count + cost estimate, no API calls
.venv/bin/python run_probes.py --limit 2    # smoke test: first 2 cases only
.venv/bin/python run_probes.py              # full run
```

Each finished call is added to `results/progress.jsonl`. If a run is interrupted, run the same command again: saved calls are skipped and failed calls are retried. Every run writes a new `results/probes_<timestamp>.xlsx` with all saved rows for the selected cases. To start from scratch, delete `results/progress.jsonl`.

## Files

- `cases.yaml`: system prompts, policy notes, and the 20 cases (with `source` URLs where a pass rule was checked).
- `run_probes.py`: the runner. Models, runs, token cap and parallelism are set in the config block at the top.

## Notes

- All three default models think before answering, and thinking tokens count toward the output cap. The cap is set to 4000 so answers aren't cut off. Any response that hits the cap is marked `[TRUNCATED]`.
- Temperature and reasoning effort are left at each provider's default. Claude Sonnet 5.5 rejects non-default temperature.
