## General

Write all comments and names in English.

Use local <project_root>/tmp for temporary files and delete them after use.

Always keep the README and ARCHITECTURE documents updated.

## Code Quality Principles

### Visibility

- Respect the visibility of methods and variables.
- Protected methods (prefixed with `_`) are NEVER called from outside their class.
- If a protected method needs to be called from outside, convert it to public (remove `_` prefix).
- Public methods must have a docstring explaining what they do.
- Do not expose internal attributes publicly unless absolutely necessary. Prefer methods that return the needed data.

### Single Responsibility Principle (SRP)

- Each class should have one clear responsibility.
- If a class does more than one thing, split it into separate classes.
- When extracting a class, group cohesive methods that share the same domain concern.
- Avoid delegation wrappers on the orchestrating class unless really needed.

### Method Complexity

- If a method is too complex or too long, split it into smaller methods.
- Use dispatcher methods that delegate to type-specific methods when handling multiple cases.
- Keep the orchestrating method short and readable; move details to helpers.

### Extraction Criteria

When deciding whether to extract a class from an existing one:

1. **Cohesion**: Do the methods share a clear, distinct responsibility?
2. **Size**: Is the group large enough to justify a separate class (typically 3+ methods or 100+ lines)?
3. **Independence**: Can the group be tested independently?
4. **Reusability**: Will the extracted class be useful beyond the original context?

Do NOT extract:
- Single small methods (not worth a class).
- Methods that are tightly coupled to many dependencies from the original class.
- Core orchestration logic that IS the class's primary responsibility.

### Naming Conventions

- Builder classes: `XxxBuilder` (e.g., `HeaderBuilder`, `TocBuilder`)
- Processor classes: `XxxProcessor` (e.g., `FootnotesProcessor`)
- Manager classes: `XxxManager` (e.g., `StyleManager`)
- Static utility methods stay on the class if they're closely related to its responsibility.

## ⛔ CRITICAL RULE: NEVER MERGE TO MAIN WITHOUT APPROVAL

After creating a branch and committing changes:
1. Inform the user that the branch is ready.
2. **WAIT** for the user's explicit approval.
3. Only after receiving approval, merge into main.
4. Delete the branch.

**Do NOT merge if the user has not said "merge." **
**Do NOT ask for approval AND merge in the same step.**
**If in doubt, STOP and ask.**

## Branching Strategy

Use Github Flow for branching strategy:
- main: production-ready code
- feature branches: for new features
- bugfix branches: for bug fixes
- hotfix branches: for hotfixes

Never commit to main branch.

Workflow for each fix/feature:
1. Create a branch from main.
2. Commit changes on the branch.
3. Ask the user for permission to merge into main. **Stop and wait.**
4. Once approved, merge into main.
5. Delete the branch after merging.

## Starting Workflow

When the user says they want to start fixing a bug or implementing a feature:
1. If not on main, switch to main first.
2. If there are uncommitted changes, warn the user before proceeding so they can commit first.

## Versioning

Follow Semantic Versioning (SemVer): MAJOR.MINOR.PATCH (e.g., 1.2.0).

- MAJOR: incompatible API changes.
- MINOR: new functionality, backwards-compatible.
- PATCH: backwards-compatible bug fixes.

Before bumping the version, propose the new version number to the user and wait for their approval before proceeding.

### Bump process

Use the `bump_version.sh` script, which updates all three version locations
(`pyproject.toml`, `data/com.github.mdtoepub.metainfo.xml`, `mdtoepub/_version.py`),
runs tests, commits, tags, and optionally pushes branch + tag to origin in one step:

```bash
./bump_version.sh 1.6.0
```

**Important:** always run `bump_version.sh` instead of manually editing `_version.py` alone,
so all files stay in sync and the metainfo release date is updated.