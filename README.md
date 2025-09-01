# LinguaSynth

# Setup
LinguaSynth uses a Makefile to start up its docker containers. See the list of available commands bellow

- command: `make start`
  - Start everything up in attached terminal
- command: `make start-d`
  - Start everything up in detached terminal
- command: `make down`
  - Shutdown all docker containers 
- command: `make down-f`
  - Shutdown all docker containers and clean up volumes
- command: `make images_delete`
  - Delete all docker images on the machine. 
- command: `make get_images`
  - Get a list of all docker images that are currently on the machine.

# Secrets / Envs
This project makes use of docker secrets (https://docs.docker.com/compose/how-tos/use-secrets/) to manage private internal environment variables.

Env variable: `SECRETS_PATH=[path to secrets files]`

## Default
By default, this project has existing .evn and secrets already setup for each container. Secret files root path can be overridden by passing in your own .env file by added `--env-file` when building / running docker compose.