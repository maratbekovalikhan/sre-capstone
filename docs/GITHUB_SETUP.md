# GitHub Repository Setup

Instructions for configuring the GitHub repository for CI/CD.

## 1. Make Repository Public

The repository must be public (assignment requirement).

Settings → General → Danger Zone → Change visibility → **Public**

## 2. Configure GitHub Actions Permissions

Settings → Actions → General:

- **Workflow permissions**: select **"Read and write permissions"**
- Check **"Allow GitHub Actions to create and approve pull requests"**

This is needed so the CD workflow can:
- Push Docker images to GHCR (packages: write)
- Commit updated image tags back to the repo (contents: write)

## 3. GitHub Container Registry (GHCR)

GHCR is enabled by default for all public repositories. The workflows use
`${{ secrets.GITHUB_TOKEN }}` automatically — no additional tokens needed.

## 4. After First Successful CD Run

1. Go to your GitHub profile → **Packages**
2. Find the `sre-capstone` package
3. Click the package → **Package settings**
4. **Change visibility** → **Public**

This allows `docker pull` without authentication.

## 5. What to Commit / What to Ignore

**DO NOT commit:**
- `.env` (local environment variables)
- `terraform.tfvars` (contains passwords)
- `*.tfstate` / `*.tfstate.backup`
- `.terraform/` directory

**DO commit:**
- `terraform.tfvars.example` (template without secrets)
- `.terraform.lock.hcl` (provider lock file)
- All workflow files in `.github/workflows/`
