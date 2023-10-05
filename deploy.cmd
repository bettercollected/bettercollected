@echo off
setlocal enabledelayedexpansion

set "user_preference=%1"

REM Array to hold selected services
set "services_to_start=mongodb mongo-seed webapp nginx backend auth postgresql temporal worker"

REM Determine the appropriate Docker Compose command
if exist "docker-compose" (
  set "docker_compose_cmd=docker-compose"
) else if exist "docker" (
  REM Check if 'docker compose' is available
  docker compose --help >nul 2>nul
  if !errorlevel! equ 0 (
    set "docker_compose_cmd=docker compose"
  ) else (
    echo Neither 'docker-compose' nor 'docker compose' is available. Please install Docker Compose.
    exit /b 1
  )
) else (
  echo Docker is not installed. Please install Docker and Docker Compose.
  exit /b 1
)

REM Common docker function
:dockerup
set "typeform_flag=false"
set "googleform_flag=false"

REM Loop through the arguments in %*
for %%i in (%*) do (
  REM Check if the current argument is equal to "integrations-typeform"
  if "%%i" == "integrations-typeform" set "typeform_flag=true"

  REM Check if the current argument is equal to "integrations-googleform"
  if "%%i" == "integrations-googleform" set "googleform_flag=true"
)

set "GOOGLE_ENABLED=!googleform_flag!"
set "TYPEFORM_ENABLED=!typeform_flag!"
"%docker_compose_cmd%" -f "docker-compose.deployment.yml" up --build -d %*

:dockerdown
"%docker_compose_cmd%" -f "docker-compose.deployment.yml" down

if /i "%user_preference%" == "both" (
  set "services=integrations-typeform integrations-googleform"
  for %%s in (%services%) do (
    set "services_to_start=!services_to_start! %%s"
  )
  call :dockerup !services_to_start!
) else if /i "%user_preference%" == "googleform" (
  set "services_to_start=!services_to_start! integrations-googleform"
  call :dockerup !services_to_start!
) else if /i "%user_preference%" == "typeform" (
  set "services_to_start=!services_to_start! integrations-typeform"
  call :dockerup !services_to_start!
) else if /i "%user_preference%" == "down" (
  call :dockerdown
) else (
  call :dockerup !services_to_start!
)

:end
endlocal
