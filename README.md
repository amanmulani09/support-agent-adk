# Support agent demo

A small FastAPI app using Google ADK and Gemini (`gemini-2.5-flash`).

- `GET /`: startup check.
- `POST /health`: health check.
- `POST /support`: accepts `message` and `user_id`; calls the agent.
- `app/agent.py`: agent instructions and a mock order lookup tool.
- Sessions live in memory. Each support request creates a new session, so this demo does not retain conversation history between requests.

## Run locally

Install Python 3.14 and uv, then:

```sh
uv sync --frozen
export GOOGLE_GENAI_USE_VERTEXAI=false
export GOOGLE_API_KEY='your-gemini-api-key'
uv run uvicorn app.main:app --reload
```

Open http://localhost:8000/docs to try the API. Never commit your API key.

## How deployment works

```text
PR merges into main
  → GitHub Actions builds a Docker image
  → starts the container and checks GET /
  → authenticates to Google Cloud
  → pushes the image to Artifact Registry (tagged with the commit SHA)
  → deploys that image to Cloud Run
```

The workflow uses `push` to `main`: direct pushes also deploy. Require PRs through a GitHub branch rule if you want only reviewed changes. One workflow handles build and deploy; no separate pipeline is needed.

Python 3.14 matches `pyproject.toml` and `.python-version`. The image installs dependencies from `uv.lock`, excludes local ADK session data, and listens on Cloud Run's `PORT`.

GitHub uses Workload Identity Federation (OIDC): short-lived credentials, with no service account JSON key stored in GitHub. A separate runtime service account lets the app call Gemini through Vertex AI without an API key.

## One-time Google Cloud setup

Run these commands in Google Cloud Shell as a project administrator. Use a project with billing enabled. They create billable infrastructure; Cloud Run and Vertex AI usage can incur charges.

1. Set your project and repository, enable APIs, and create an image repository and service accounts:

```sh
export PROJECT_ID='your-google-cloud-project-id'
export GITHUB_REPOSITORY='amanmulani09/support-agent-adk'
export REGION='us-central1'
gcloud config set project "$PROJECT_ID"
export PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"

gcloud services enable run.googleapis.com artifactregistry.googleapis.com \
  aiplatform.googleapis.com iam.googleapis.com iamcredentials.googleapis.com \
  sts.googleapis.com cloudresourcemanager.googleapis.com

gcloud artifacts repositories create support-agent \
  --repository-format=docker --location="$REGION"
gcloud iam service-accounts create github-deployer
gcloud iam service-accounts create support-agent-runtime

gcloud artifacts repositories add-iam-policy-binding support-agent \
  --location="$REGION" \
  --member="serviceAccount:github-deployer@$PROJECT_ID.iam.gserviceaccount.com" \
  --role=roles/artifactregistry.writer
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:github-deployer@$PROJECT_ID.iam.gserviceaccount.com" \
  --role=roles/run.admin
gcloud iam service-accounts add-iam-policy-binding \
  "support-agent-runtime@$PROJECT_ID.iam.gserviceaccount.com" \
  --member="serviceAccount:github-deployer@$PROJECT_ID.iam.gserviceaccount.com" \
  --role=roles/iam.serviceAccountUser
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:support-agent-runtime@$PROJECT_ID.iam.gserviceaccount.com" \
  --role=roles/aiplatform.user
```

2. Allow GitHub workflows from this repository's `main` branch to impersonate the deployer:

```sh
gcloud iam workload-identity-pools create github \
  --location=global --display-name='GitHub Actions'
gcloud iam workload-identity-pools providers create-oidc github \
  --location=global \
  --workload-identity-pool=github \
  --issuer-uri='https://token.actions.githubusercontent.com' \
  --attribute-mapping='google.subject=assertion.sub,attribute.repository=assertion.repository' \
  --attribute-condition="assertion.repository == '$GITHUB_REPOSITORY' && assertion.ref == 'refs/heads/main'"
gcloud iam service-accounts add-iam-policy-binding \
  "github-deployer@$PROJECT_ID.iam.gserviceaccount.com" \
  --role=roles/iam.workloadIdentityUser \
  --member="principalSet://iam.googleapis.com/projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/github/attribute.repository/$GITHUB_REPOSITORY"

echo "GCP_PROJECT_ID=$PROJECT_ID"
echo "GCP_WORKLOAD_IDENTITY_PROVIDER=projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/github/providers/github"
```

IAM changes can take a few minutes to propagate.

3. In GitHub → Settings → Secrets and variables → Actions → Variables, add the two repository variables printed above: `GCP_PROJECT_ID` and `GCP_WORKLOAD_IDENTITY_PROVIDER`. No GitHub secrets are required for this setup.

4. Commit these files, including `Dockerfile`, `.dockerignore`, `pyproject.toml`, and `uv.lock`, then merge a PR into `main`. Follow **Deploy to Cloud Run** in the Actions tab. The setup names and region must match `.github/workflows/deploy.yml`.

## Try the deployed demo

Cloud Run requires authentication. As a user with `roles/run.invoker` on the service (or an administrator), run this locally with the Google Cloud CLI:

```sh
gcloud run services proxy support-agent-adk \
  --project "$PROJECT_ID" --region us-central1 --port 8080
```

Open http://localhost:8080/docs, or use another terminal:

```sh
curl --fail http://localhost:8080/support \
  -H 'Content-Type: application/json' \
  -d '{"message":"Where is order 12345?","user_id":"demo-user"}'
```

The workflow's smoke check verifies container startup, not a live Gemini call. The request above verifies Vertex AI access and the agent end to end after deployment.

Demo limits: mock order data, no persistent sessions, and no automated agent tests. Cloud Run scales to zero and is configured for at most one instance to keep this demo small; this is not a spending cap. Delete the Cloud Run service and Artifact Registry repository when finished to remove the deployed app and stored images.

References: [GitHub workflow triggers](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#push), [Google Cloud authentication action](https://github.com/google-github-actions/auth), [Cloud Run container contract](https://cloud.google.com/run/docs/container-contract).
