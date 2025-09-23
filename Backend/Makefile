# ──────────────────────────────────────────────────────────────────────────────
# Start docker containers in a detached terminal 
# ──────────────────────────────────────────────────────────────────────────────
start:
	docker compose up -d 
# ──────────────────────────────────────────────────────────────────────────────
# Builds and starts the docker containers  
# ──────────────────────────────────────────────────────────────────────────────
start-build:
	docker compose up --build -d 
# ──────────────────────────────────────────────────────────────────────────────
# Shutdown all docker containers 
# ──────────────────────────────────────────────────────────────────────────────
stop:
	docker compose down 
# ──────────────────────────────────────────────────────────────────────────────
# Shutdown all docker containers and clean up volumes
# ──────────────────────────────────────────────────────────────────────────────
stop-prune:
	docker compose down -v --remove-orphans
	docker volume prune -f
# ──────────────────────────────────────────────────────────────────────────────
# Delete all docker images on the machine. 
# ──────────────────────────────────────────────────────────────────────────────
images_delete:
	docker rm -vf $(docker ps -aq) 
	docker rmi -f $(docker images -aq)

# ──────────────────────────────────────────────────────────────────────────────
# Cleans up all files generated during runtime
# ──────────────────────────────────────────────────────────────────────────────
clean:
	rm -rf LinguaSynth/app/Logs
# ──────────────────────────────────────────────────────────────────────────────
# Runs all test cases. 
# ──────────────────────────────────────────────────────────────────────────────
# Default tests 
test: pytest_up pytest_wait 
	@docker exec linguaSynth uv run -m --active pytest || { make pytest_down; exit 1; }
	$(MAKE) pytest_down

test-it: pytest_up pytest_wait 
	@docker exec -it linguaSynth uv run -m --active pytest -s || { make pytest_down; exit 1; }

# Bring up containers if not already running
pytest_up:
	@if [ -z "$$(docker ps -q -f name=linguaSynth)" ]; then \
		echo "Containers not running. Starting with docker compose up -d..."; \
		docker compose up -d; \
	else \
		echo "Containers already running."; \
	fi

# Wait for linguaSynth to become healthy
pytest_wait:
	@echo "Waiting for linguaSynth to become healthy..."
	@until [ "$$(docker inspect --format='{{.State.ExitCode}}' linguaSynth 2>/dev/null)" = 0 ]; do \
		status=$$(docker inspect --format='{{.State.ExitCode}}' linguaSynth 2>/dev/null); \
		echo "  Current status: $$status"; \
		sleep 2; \
	done
	@echo "\nlinguaSynth is healthy!"

# Stop all running containers after the tests have finished
pytest_down:
	@echo "Tests finished stopping containers..."
	@docker compose down -v --remove-orphans