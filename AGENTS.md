## General

Write all comments and names in English.

Use local <project_root>/tmp for temporary files and delete them after use.

Always keep the README and ARCHITECTURE documents updated.

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
3. Ask the user for permission to merge into main.
4. If they agree, merge into main.
5. Delete the branch after merging.

## Starting Workflow

When the user says they want to start fixing a bug or implementing a feature:
1. If not on main, switch to main first.
2. If there are uncommitted changes, warn the user before proceeding so they can commit first.