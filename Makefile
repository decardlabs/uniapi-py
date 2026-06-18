.PHONY: install dev build test

install:
	cd web && yarn install

dev:
	cd web && yarn dev &

build:
	cd web && yarn build

test:
	python3 -m pytest tests/ -v --no-header

run:
	python3 -m uvicorn app.main:app --port 8000 --reload
