# ──────────────────────────────────────────────────────────────────────────────
# Start everything up in attached terminal
# ──────────────────────────────────────────────────────────────────────────────
start:
	docker compose up 
# ──────────────────────────────────────────────────────────────────────────────
# Start everything up in detached terminal
# ──────────────────────────────────────────────────────────────────────────────
start-d:
	docker compose up -d 
# ──────────────────────────────────────────────────────────────────────────────
# Shutdown all docker containers 
# ──────────────────────────────────────────────────────────────────────────────
stop:
	docker compose down 
# ──────────────────────────────────────────────────────────────────────────────
# Shutdown all docker containers and clean up volumes
# ──────────────────────────────────────────────────────────────────────────────
stop-f:
	docker compose down -v --remove-orphans
	docker volume prune -f
# ──────────────────────────────────────────────────────────────────────────────
# delete all docker images on the machine. 
# ──────────────────────────────────────────────────────────────────────────────
images_delete:
	docker rmi -f $(sudo docker images -aq) 
# ──────────────────────────────────────────────────────────────────────────────
# Get a list of all docker images that are currently on the machine.
# ──────────────────────────────────────────────────────────────────────────────
get_images:
	docker images

ignore_test:
	curl http://localhost:11434/api/generate -d '{ "model": "dolphin3:8b", "prompt":" Why is the colour of sea blue ?" }'