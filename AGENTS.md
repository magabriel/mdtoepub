## General

Write all comments and names in English.

Use local <project_root>/tmp for temporary files and delete them after use.

Always keep the README and ARCHITECTURE documents updated.

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

After merging a version bump into main, create an annotated git tag: `git tag -a vX.Y.Z -m "vX.Y.Z"`.