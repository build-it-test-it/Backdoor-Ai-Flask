---
name: GitHub
type: knowledge
version: 1.0.0
agent: CodeActAgent
triggers:
  - github
  - git
  - repository
  - repo
  - pull request
  - pr
  - issue
  - commit
  - branch
  - clone
  - fork
  - merge
---

# GitHub Microagent

This microagent provides knowledge and capabilities for working with GitHub repositories.

## Authentication

To use GitHub functionality, you need a GitHub token with appropriate permissions. The token should be set in the environment variable `GITHUB_TOKEN`.

## API Usage

Use the GitHub API for operations instead of a web browser. The base URL for the GitHub API is `https://api.github.com`.

Example of using the GitHub API with curl:

```bash
curl -H "Authorization: Bearer $GITHUB_TOKEN" https://api.github.com/user
```

## Common Operations

### Cloning a Repository

```bash
git clone https://github.com/username/repo.git
# Or with token
git clone https://${GITHUB_TOKEN}@github.com/username/repo.git
```

### Creating a Branch

```bash
git checkout -b new-branch-name
```

### Committing Changes

```bash
git add .
git commit -m "Commit message"
```

### Pushing Changes

```bash
git push origin branch-name
```

### Creating a Pull Request

Use the GitHub API to create a pull request:

```bash
curl -X POST \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github.v3+json" \
  https://api.github.com/repos/owner/repo/pulls \
  -d '{
    "title": "Pull request title",
    "body": "Pull request description",
    "head": "branch-name",
    "base": "main"
  }'
```

## Best Practices

1. Never push directly to the `main` or `master` branch
2. Use descriptive commit messages
3. Create a new branch for each feature or bug fix
4. Keep pull requests focused on a single issue
5. Use draft pull requests for work in progress
6. Reference issues in commit messages and pull requests

## Error Handling

Common GitHub errors:

- 401: Authentication failed (check token)
- 403: Rate limit exceeded or insufficient permissions
- 404: Repository not found
- 422: Validation failed (check request body)

## Security Considerations

1. Never expose GitHub tokens in code or commit them to repositories
2. Use the minimum required permissions for tokens
3. Rotate tokens regularly
4. Be cautious with repository visibility settings