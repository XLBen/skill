#!/usr/bin/env python3
"""S21 read-only corpus replay runner.

Imports docs/po-repair/tools/collect_corpus.py unchanged and only redirects its
output directory (CORPUS) into baseline/s21/corpus-replay/. The sandbox source
tree is never written; docs/po-repair/corpus/ is never written.
"""

import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
TOOL = REPO / "docs" / "po-repair" / "tools" / "collect_corpus.py"
assert (REPO / "scripts" / "product_observation.py").exists(), REPO

spec = importlib.util.spec_from_file_location("collect_corpus", TOOL)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.CORPUS = REPO / "docs" / "po-repair" / "baseline" / "s21" / "corpus-replay"
raise SystemExit(module.main())
