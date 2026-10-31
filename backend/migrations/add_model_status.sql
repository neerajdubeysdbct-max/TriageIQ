-- Keep the model's own prediction separately from analyst labels (human_override),
-- so accuracy on a dataset can be measured against the analysts' answers.
ALTER TABLE tickets ADD COLUMN IF NOT EXISTS model_status VARCHAR;

-- Backfill uploads scored before this column existed (no analyst labels yet)
UPDATE tickets
SET model_status = CASE
        WHEN is_already_automated THEN 'Already Automated'
        WHEN can_be_automated THEN 'Can Be Automated'
        ELSE 'Manual Only'
    END
WHERE model_status IS NULL
  AND automation_confidence ~ '^[0-9.]+$'
  AND (human_override IS NULL OR human_override = '');

-- How a labelled ticket was chosen: random_sample (unbiased, used to measure
-- accuracy), uncertainty_queue (least confident first), ticket_view (ad hoc)
ALTER TABLE tickets ADD COLUMN IF NOT EXISTS label_source VARCHAR;
