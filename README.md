# Tesla Job Tracker

Tracks new **Tesla US Full-Time** postings by stable Req ID. It uses SQLite as the source of truth and writes `output\Tesla_New_Jobs.xlsx` for review. `Apply?` is deliberately manual.

## Verified Tesla source

The tracker uses Tesla's public careers-state endpoint:

`https://www.tesla.com/cua-api/apps/careers/state`

Tesla's careers UI fetches a single, global compact JSON state rather than server-paginated results. The state has `listings` (including `id`, `t`, `l`, `dp`, `y`) and `lookup` (`locations`, `departments`, `types`). Tesla's `site=US` and `type=fulltime` URL filters are applied from those metadata values; this tracker applies the equivalent US and Full-Time filtering locally. The endpoint does **not** expose a posting/created timestamp, so `Posted Date` remains blank and `First Seen` is the tracker discovery time. Job links are generated as Tesla's canonical `.../search/job/tjt-<Req ID>` URL.

There is no request pagination: one state response contains the full global inventory. The tracker sends only one request per run (with retries only after transient failures).

## Requirements and installation

Install Python 3.10+ for Windows, then in this project directory run PowerShell:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\install.ps1
```

The installer creates `.venv`, installs dependencies, performs a read-only connectivity test, and creates **Tesla Job Tracker - Daily 11AM**. If Tesla blocks the network request, setup stops safely and logs the error instead of creating a misleading baseline.

## First baseline and normal use

After installation, establish the baseline (existing listings will not be added to New Jobs). All baseline listings receive today's `Date Discovered` by default:

```powershell
.\run.bat --baseline
```

To use a specific date for the existing inventory instead, such as August 1, 2026:

```powershell
.\run.bat --baseline --baseline-date 2026-08-01
```

If a baseline already exists, update only its original listings without affecting jobs discovered later:

```powershell
.\run.bat --set-baseline-date 2026-08-01
```

Normal manual run:

```powershell
.\run.bat
```

Useful options:

- `--dry-run` fetches and calculates changes without changing SQLite or Excel.
- `--baseline` deliberately replaces the saved inventory with the current one and clears New Jobs discoveries from the database.
- `--force` allows an empty database to treat current jobs as new; it is intended only for testing.
- `--import-state FILE` processes a manually saved Tesla `careers/state` JSON response without making a network request. It supports files named `.txt` as well as `.json`.

For example, after copying the Network response into `lol.txt`:

```powershell
.\run.bat --import-state .\lol.txt
```

On an empty database this creates the initial baseline; append `--baseline` if you deliberately want to reset an existing baseline.

## Files

- `output\Tesla_New_Jobs.xlsx`: `New Jobs` (only jobs discovered after a baseline) and `All Jobs` (current complete inventory). `Date Discovered` records the local calendar date the tracker first found each job; newer discoveries are first. The URL cells are clickable.
- `data\tesla_jobs.db`: historical jobs and `scans` run history; historical job records are never deleted during normal scans.
- `logs\tesla_job_tracker.log`: endpoint, counts, successes, and errors.

## Scheduled task

The PowerShell installer registers a Windows Task Scheduler task for 11:00 AM every day under the installing Windows user. It calls `.venv\Scripts\python.exe -m src.main` with this project as the working directory. `StartWhenAvailable` tells Windows to run the missed task when the computer becomes available; Windows policy and power state can still affect when that happens. View, run, or remove it with:

```powershell
Get-ScheduledTask -TaskName 'Tesla Job Tracker - Daily 11AM'
Start-ScheduledTask -TaskName 'Tesla Job Tracker - Daily 11AM'
Unregister-ScheduledTask -TaskName 'Tesla Job Tracker - Daily 11AM' -Confirm:$false
```

## Tests and troubleshooting

Run tests after installation:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

If a run says HTTP 403/429 or "Access Denied", Tesla has blocked the request from that network. The tracker does not circumvent blocks, CAPTCHAs, or rate limits. Retry later, confirm `https://www.tesla.com/careers/search/?type=fulltime&site=US` opens normally from the same PC, then check the log. If Tesla changes the JSON shape, the log reports the expected `listings`/`lookup` structure.
