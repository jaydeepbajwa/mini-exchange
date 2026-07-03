.PHONY: demo api test frontend-build

demo:
	docker compose up --build

api:
	mini-exchange-api

test:
	python3 scripts/lint.py
	python3 -m compileall mini_exchange scripts tests
	python3 -m unittest discover -s tests -p "test_*.py"

frontend-build:
	npm --prefix frontend run build
