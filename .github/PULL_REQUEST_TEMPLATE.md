## What changes

## Checklist (see CONTRIBUTING.md §6)

- [ ] `python build_pages.py` runs and the generated files are committed
- [ ] `python selfcheck.py` and `python -m pytest tests -q` are green
- [ ] `python tools/golden.py` shows only additions — or every change is explained in `CHANGELOG.md`
- [ ] New or changed references were checked with `python tools/check_citations.py`
- [ ] Text visible on the site has an English version (`data/i18n/*.json`, or `summary_en` / `name_en` fields for pages)
