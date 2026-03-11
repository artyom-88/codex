# GitHub Workflow

- After creating and pushing a feature branch, automatically open a pull request unless the user explicitly says not to.
- Default the pull request base branch to `main`.
- Default the pull request title to the latest commit subject unless the user requests a different title.
- Default the pull request body to a concise summary generated from the commit range or diff.
- Create ready-for-review pull requests by default. Use draft only when the user asks for it or the work is clearly not ready.
- If `gh pr create` is blocked by auth or approval requirements, request the needed approval or ask the user to authenticate with `gh auth login`.
