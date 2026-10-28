# Contributing to LedgerShield

Start with the [README](README.md), [initial audit](docs/IMPLEMENTATION_AUDIT.md), and [architecture](docs/architecture.md). Preserve working components and document research assumptions.

1. Fork and clone `https://github.com/manikantbindass/LedgerShield.git`.
2. Create a focused branch and follow the README's Python 3.12 / Node 24 setup.
3. Keep autonomous disruptive actions restricted to the local simulator. Never lower quorum to make recovery appear successful.
4. Add meaningful regression tests for behavior changes. Use distinct seeds for training and evaluation; report baseline comparisons accurately.
5. Run `python -m pytest -q` with the virtual environment, then `npm run lint` and `npm run build` in `frontend`.
6. Use concise conventional commits and explain the problem, resulting behavior, validation and limitations in the pull request.

Do not commit secrets, private signing keys, generated datasets, checkpoints, virtual environments or build output. Reproducible demo keys are public simulator identities, not real wallet keys. Report observed behavior and reproduction steps in [GitHub issues](https://github.com/manikantbindass/LedgerShield/issues).

No production-readiness, formal Byzantine-tolerance, attack-prevention or model-improvement claim should exceed the available test and evaluation evidence. The repository does not yet contain a license grant.
