# Key Questions

  1. Deployment Environment:
    - Where do you want to run the pipeline? (Your local machine, cloud service like AWS/GCP, self-hosted server?)
    - Do you have any preferences for orchestration? (Cron jobs, Airflow, GitHub Actions, simple scripts?)
  2. Data Storage:
    - Where should processed data be stored? (Local disk, S3/Cloud Storage, both?)
    - Should the pipeline also push data directly to GraphHopper, or just prepare files?
  3. GraphHopper Deployment:
    - Will GraphHopper run on the same machine as the pipeline, or separately?
    - Self-hosted or cloud-hosted GraphHopper?
  4. Update Frequency:
    - You mentioned weekly updates - is that firm, or should it be configurable?
    - Should it also support manual/on-demand runs?
  5. MVP Scope:
    - Start with Norway only (as discussed), correct?
    - Should the pipeline structure be ready for multi-country from day one, or add that later?
  6. Error Handling:
    - If Geonorge is down or data is corrupted, should it:
        - Skip update and keep old data?
      - Send notifications (email, Slack)?
      - Retry automatically?
  7. Data Validation:
    - Should the pipeline validate the processed data before deploying to GraphHopper?
    - What if trail data is significantly different from last week (trails removed/added)?
  8. Integration with Current Project:
    - Should this be part of the trails Python package, or separate?
    - Reuse existing code from trails.io.sources.geonorge, or refactor?

Please answer these so I can create a well-designed implementation plan!
