# Claude Development Notes

## Branch Workflow

**Always start changes by making a new branch from main, rather than adding to older branches.**

### Standard Workflow

1. Start from an updated `main` branch
2. Create a fresh feature branch for each new set of changes
3. Never reuse or continue work on old branches

### Commands

```bash
git checkout main
git pull origin main
git checkout -b claude/descriptive-name-W721s
# make changes
# commit and push
```

### Benefits

- Keeps each PR focused on a single feature/fix
- Makes branch management cleaner
- Works better with repository branch protection rules
- Each branch starts clean from protected main
- Easier to review and understand changes
- Simpler to revert if needed

## Repository Setup

- **Main branch:** Protected with branch rules
- **Status checks required:** "Lint Code" and "Build Hugo Site"
- **Changes to main:** Must go through pull requests
- **Feature branches:** Can be freely merged/rebased
