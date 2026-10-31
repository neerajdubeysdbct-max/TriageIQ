#!/bin/sh
# Container start: migrate the database, train the models on the bundled synthetic
# data if none are present yet, create the first admin if asked to, then serve.
set -e

python migrate.py

if [ ! -f models/automation_classifier.joblib ]; then
    echo "No trained models found: training on the synthetic Northwind data (about a minute)"
    python train_automation_model.py --tickets "$BASE_TRAINING_TICKETS" --labels "$BASE_TRAINING_LABELS"
    python train_category_model.py --tickets "$BASE_TRAINING_TICKETS" --labels "$BASE_TRAINING_LABELS"
fi

if [ -n "$ADMIN_USERNAME" ] && [ -n "$ADMIN_PASSWORD" ]; then
    python create_admin.py
fi

exec uvicorn main:app --host 0.0.0.0 --port 8000
