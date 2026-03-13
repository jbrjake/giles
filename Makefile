VENV := .venv
PYTHON := $(VENV)/bin/python

.PHONY: test test-unit test-integration test-golden lint venv help

venv: $(VENV)/bin/activate  ## Create local venv (Python 3.10)

$(VENV)/bin/activate:
	python3 -m venv $(VENV)
	@echo "venv created at $(VENV)/"

test: venv  ## Run all tests
	$(PYTHON) -m unittest discover -s tests -v

test-unit: venv  ## Run only fast unit tests
	$(PYTHON) -m unittest tests.test_gh_interactions -v

test-integration: venv  ## Run lifecycle + hexwise integration tests
	$(PYTHON) -m unittest tests.test_lifecycle tests.test_hexwise_setup -v

test-golden: venv  ## Run golden recording replay
	$(PYTHON) -m unittest tests.test_golden_run -v

test-golden-record: venv  ## Re-record golden snapshots
	GOLDEN_RECORD=1 $(PYTHON) -m unittest tests.test_golden_run -v

lint: venv  ## Check Python syntax (stdlib only, no linter deps)
	$(PYTHON) -m py_compile scripts/validate_config.py
	$(PYTHON) -m py_compile scripts/sprint_init.py
	$(PYTHON) -m py_compile scripts/sprint_teardown.py
	$(PYTHON) -m py_compile scripts/commit.py
	$(PYTHON) -m py_compile scripts/sync_backlog.py
	$(PYTHON) -m py_compile scripts/manage_epics.py
	$(PYTHON) -m py_compile scripts/manage_sagas.py
	$(PYTHON) -m py_compile scripts/sprint_analytics.py
	$(PYTHON) -m py_compile scripts/team_voices.py
	$(PYTHON) -m py_compile scripts/test_coverage.py
	$(PYTHON) -m py_compile scripts/traceability.py
	$(PYTHON) -m py_compile skills/sprint-setup/scripts/bootstrap_github.py
	$(PYTHON) -m py_compile skills/sprint-setup/scripts/populate_issues.py
	$(PYTHON) -m py_compile skills/sprint-setup/scripts/setup_ci.py
	$(PYTHON) -m py_compile skills/sprint-run/scripts/sync_tracking.py
	$(PYTHON) -m py_compile skills/sprint-run/scripts/update_burndown.py
	$(PYTHON) -m py_compile skills/sprint-monitor/scripts/check_status.py
	$(PYTHON) -m py_compile skills/sprint-release/scripts/release_gate.py
	$(PYTHON) -m py_compile scripts/verify_line_refs.py
	$(PYTHON) scripts/verify_line_refs.py

clean:  ## Remove venv and __pycache__
	rm -rf $(VENV) **/__pycache__

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'
