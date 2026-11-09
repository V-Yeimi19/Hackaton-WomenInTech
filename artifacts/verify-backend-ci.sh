#!/usr/bin/env sh
set -eu
python -m venv /tmp/mica-ci
/tmp/mica-ci/bin/python -m pip install --quiet -r requirements.lock -e '.[dev]'
/tmp/mica-ci/bin/python -m ruff check .
/tmp/mica-ci/bin/python -m ruff format --check app tests migrations
/tmp/mica-ci/bin/python -m mypy app
/tmp/mica-ci/bin/python -m alembic upgrade head
/tmp/mica-ci/bin/python -m pytest --cov=app --cov-report=term-missing --junitxml=/tmp/backend-test-results.xml -p no:cacheprovider
/tmp/mica-ci/bin/python -m app.jobs.worker --once
/tmp/mica-ci/bin/python -m app.jobs.scheduler --once
printf '\nBACKEND_CI_OK\n'
