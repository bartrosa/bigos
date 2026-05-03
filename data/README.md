# data/

This directory is for your local document samples used in sanity checks. Files here are gitignored — do not commit private documents.

Recommended workflow:

```bash
# drop 5-10 representative PDFs into this directory, then:
uv run python scripts/sanity_check.py data/ --output-md-dir=data/_parsed/
```

Open `data/_parsed/*.md` in VS Code and visually verify quality.
