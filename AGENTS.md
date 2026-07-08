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

Always ask the user for permission to merge feature/bugfix/hotfix branches into develop, and develop into main.

After a successful merge, delete the feature/bugfix/hotfix branch.