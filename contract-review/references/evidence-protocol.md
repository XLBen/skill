# Evidence Protocol

> When to read: when a material fact is disputed and research or prototype
> work is about to start.

Research only a claim that can change P/W/D/A/F/I/V or close a surviving
issue. Prefer official specifications, official documentation, source and
maintainer records, then reproducible experiments. Secondary sources locate
primary evidence but do not settle a critical claim.

An E node records claim, source revision, checked time, environment, command,
fixed inputs, output summary, verdict, redaction metadata, and a mandatory
`bundle_hash`. Prototype code is excluded from production unless separately
adopted, but its reproducibility bundle remains available for audit.

Never persist credentials, tokens, passwords, or unnecessary PII. Record only
the environment variable or secret-manager reference and the redaction type.

When two agents dispute observable behavior, convert it into one falsifiable
experiment with a predeclared outcome interpretation. Stop when the configured
research/prototype budget is exhausted and request owner control; do not keep
browsing because more evidence might exist.
