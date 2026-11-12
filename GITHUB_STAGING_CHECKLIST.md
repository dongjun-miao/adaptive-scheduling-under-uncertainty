# GitHub staging checklist (private-first)

This folder was prepared from the audited research portfolio for the GitHub account `dongjun-miao`.

## Before publication

1. Create the repository `dongjun-miao/adaptive-scheduling-under-uncertainty` using GitHub Desktop or GitHub web UI, choosing **Private** initially. Repository creation must be done by the account holder because the currently connected integration does not expose repository creation.
2. Copy these folder contents into the newly initialized local repo, review changes in GitHub Desktop, commit and push.
3. Validate with the commands in README (Python 3.12 tested on original Windows environment).
4. Confirm `scripts/fetch_benchmark.py` retrieves the pinned upstream fixture and matches its SHA256. It intentionally does not redistribute the benchmark.
5. Run `scripts/extract_results.py` once to restore complete research logs. The expanded log files are ignored by Git; do not blindly commit 170+ MB of JSON.
6. Confirm correct public author info. Existing research PDF/one-page summary are **drafts without personal identity** and should be regenerated after the repository URL is live.
7. Check all files for privacy, license, repo description, and citation accuracy; choose a license for your own work before opening public.
8. Change visibility to Public only after review; then pin repository to the profile and update its README.

## Notes

- The compressed raw log archive is retained in the repo for independent verification. Source data can be restored locally.
- No new scientific results were generated. No source code or benchmark results changed.
- The full-size raw experiment JSON files were omitted from the Git tree (but stored losslessly in a compressed archive).
- No benchmark instance was embedded due to pending source-level rights verification.
- Do not use the anonymous PDF drafts as final RA attachments.
