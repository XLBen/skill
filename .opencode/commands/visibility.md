---
description: Select or inspect this project's observation model (used by product-observer)
agent: build
---

Select the project-scoped observation model for:

$ARGUMENTS

Always resolve the request through the real host catalog first. Run (no
argument means the default request `gpt 5.6 luna`):

    python .opencode/workflow/scripts/visibility_config.py set --project . --request "<name or provider/model>"

The command prints JSON on stdout and exits 0 selected / 3 needs-selection /
4 not-found / 2 error.

1. Exit 3 (`needs-selection`): the request matches several real models. Show
   the returned `candidates` to the user with the `question` tool, then persist
   their explicit pick with
   `python .opencode/workflow/scripts/visibility_config.py select --project . --model <full>`.
   Never choose on the user's behalf and never invent a model id.
2. Exit 4 (`not-found`): the request matches nothing in the catalog. Show the
   first entries of `opencode models` (or the error from the failed catalog
   read) and ask for a corrected name; do not fabricate a model.
3. On success report: the actual `provider/model` persisted, the capability
   statuses (`image` / `video` / `audio` from the same JSON), and the scope -
   this setting only selects the observation model for this project's skill
   workflow. It does not change the main chat model or any global OpenCode
   configuration.
4. Be honest about effect: the selection is read by the next observation
   dispatch. If the host must reload code to pick it up, say that a restart is
   required instead of claiming the switch is live.

Inspect the current setting at any time with
`python .opencode/workflow/scripts/visibility_config.py show --project .`
(`status: unconfigured` means nothing has been chosen yet). Record real
capability probe results with
`python .opencode/workflow/scripts/visibility_config.py mark --project . --capability image --status verified --evidence <reference>`;
`verified` without evidence is refused.
