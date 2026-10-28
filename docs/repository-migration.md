# Repository URL migration

Target repository: `manikantbindass/ledgershield-ai`. Product display name remains LedgerShield. This is a rename of the existing repository, preserving history and main; not a new repository or force push.

Before renaming, inspect `git remote -v`, `git status --short`, current branch and HEAD. Commit verified changes first; do not reset the working tree. Existing repository was verified as manikantbindass/LedgerShield with default branch main. README/setup/contribution links are prepared for the target.

If a rename operation is unavailable: open the existing GitHub repository → Settings → General → Repository name → enter `ledgershield-ai` → Rename. A file commit cannot rename GitHub metadata. After the actual rename:

```bash
git remote set-url origin https://github.com/manikantbindass/ledgershield-ai.git
git remote -v
git branch --show-current
git log -1 --oneline
git fetch origin
```

Verify GitHub still shows main as default and the prior commits remain. Existing clones keep their local folder name unless their owner renames it separately. Use the new URL for clone commands; do not rely indefinitely on redirect behavior. No workflow depends on the old repository path.
