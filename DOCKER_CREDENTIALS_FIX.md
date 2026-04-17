# Docker Google Cloud Credentials Fix

## Problem
The agent decision endpoint was failing in Docker with:
```
google.auth.exceptions.DefaultCredentialsError: File  was not found.
```

This occurred because the `GOOGLE_APPLICATION_CREDENTIALS` environment variable wasn't properly configured for the Docker/Linux environment.

## Root Cause
- In Windows, relative paths work fine (e.g., `app/secrets/file.json`)
- In Docker, the environment variable was either empty or pointing to a non-existent path
- The credentials file was mounted but the path wasn't correctly set

## Solution

### Changes Made

1. **`docker-compose.yml`** - Hardcoded absolute paths for Docker container:
   - Set `GOOGLE_CLOUD_PROJECT=dynalunch`
   - Set `GOOGLE_APPLICATION_CREDENTIALS=/app/app/secrets/dynalunch-d1e92e06a11a.json`

2. **`config.py`** - Improved error handling and logging:
   - Better debug messages for credential path resolution
   - Added file existence check before setting environment variable
   - Clear warning messages when credentials are missing

3. **`.env.example`** - Updated documentation:
   - Clarified different path formats for Windows vs Docker
   - Added comments explaining when to use relative vs absolute paths

## Testing

### Restart Docker Containers
```powershell
docker-compose down
docker-compose up --build
```

### Test the Agent Decision Endpoint
Make a POST request to the agent decision endpoint with a team that has members and preferences set up.

### Expected Debug Output
You should see in the Docker logs:
```
[DEBUG] GOOGLE_APPLICATION_CREDENTIALS from settings: /app/app/secrets/dynalunch-d1e92e06a11a.json
[DEBUG] Credentials file exists at /app/app/secrets/dynalunch-d1e92e06a11a.json: True
[DEBUG] Set OS environment variable GOOGLE_APPLICATION_CREDENTIALS
```

## Notes

- The credentials file is mounted as read-only (`:ro`) for security
- The volume mount `./backend/app/secrets:/app/app/secrets:ro` ensures the file is available in the container
- For local Windows development, use relative paths in your `.env` file
- For Docker, the paths are now hardcoded in `docker-compose.yml`
