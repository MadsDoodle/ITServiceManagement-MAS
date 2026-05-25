# GitHub Personal Access Token Setup Guide

This guide explains how to generate and configure a GitHub Personal Access Token (PAT) for the Agentic ITSM platform.

The token will allow the AI agents to:

* create GitHub issues,
* update GitHub Projects,
* move incident workflow cards,
* read commits and deployments,
* and automate operational workflows.

---

## STEP 1 — OPEN GITHUB TOKEN SETTINGS

Open:

https://github.com/settings/tokens

Then navigate to:

Generate new token
→ Generate new token (classic)

---

## STEP 2 — TOKEN NAME

Set a descriptive token name.

Recommended:

agentic-itsm-token

---

## STEP 3 — EXPIRATION

Recommended options:

* 90 days
* or No expiration (for local development only)

---

## STEP 4 — SELECT REQUIRED SCOPES

Select ONLY the following scopes.

Required:

1. repo
   Purpose:

* create/update issues
* read commits
* access repositories
* manage operational tickets

---

2. workflow
   Purpose:

* monitor GitHub Actions workflows
* inspect CI/CD failures
* support deployment monitoring

---

3. project
   Purpose:

* access GitHub Projects
* move workflow cards
* update incident fields
* manage operational lifecycle states

---

Optional:

4. read:org
   Only needed if using organization repositories later.

---

## IMPORTANT SECURITY NOTE

DO NOT select unnecessary scopes such as:

* delete_repo
* admin scopes
* enterprise scopes
* billing scopes
* package scopes
* codespaces scopes

The token should use minimal permissions required for operational automation.

---

## STEP 5 — GENERATE TOKEN

Click:

Generate token

IMPORTANT:
GitHub will only show the token ONCE.

Immediately copy and securely store the token.

---

## STEP 6 — CREATE .env FILE

Inside:

agentic-itsm/

create a file named:

.env

---

## STEP 7 — ADD GITHUB CONFIGURATION

Add the following:

GITHUB_TOKEN=your_generated_token_here
GITHUB_REPO_OWNER=MadsDoodle
GITHUB_REPO_NAME=ITServiceManagement-MAS
GITHUB_PROJECT_NUMBER=your_project_number

---

## STEP 8 — GET PROJECT NUMBER

Open your GitHub Project.

Example URL:

https://github.com/users/MadsDoodle/projects/3

The final number:

3

is your:

GITHUB_PROJECT_NUMBER

Example:

GITHUB_PROJECT_NUMBER=3

---

## STEP 9 — PROTECT THE TOKEN

Ensure `.gitignore` contains:

.env

Never commit secrets or tokens to GitHub.

---

## STEP 10 — VERIFY ACCESS

The token should now allow the Agentic ITSM platform to:

* create issues,
* update project cards,
* move workflow states,
* and automate GitHub operational workflows.

---

## EXPECTED FUTURE USAGE

The token will later be used by:

* GitHub Operations Agent
* Root Cause Analysis workflows
* Incident lifecycle automation
* GitHub Project state management
* Deployment correlation systems

within the LangGraph-based Agentic ITSM orchestration platform.
