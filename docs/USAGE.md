Usage and CLI

Basic usage

Run the application in interactive mode:

```bash
python src/app.py
```

Validation example

```bash
python src/app.py --validate "Text to validate"
```

Sourcing facts

To request synthesis from explicit sources, include a `SOURCES:` block in your input. Example:

```
Please summarize these documents.
SOURCES: [
  {"title": "Spec A", "id": "spec-a", "url": "https://example.com/spec-a"},
  {"title": "Spec B", "id": "spec-b"}
]
```

The assistant will only synthesize from the provided sources and will refuse if no verified sources are supplied.
