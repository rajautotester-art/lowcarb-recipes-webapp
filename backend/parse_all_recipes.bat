@echo off
setlocal
cd /d C:\lowcarb-recipe-chatbot\backend
".venv\Scripts\python.exe" scripts\parse_recipe_files.py
if errorlevel 1 (
  echo.
  echo Parser failed. Check the error above.
  exit /b 1
)
echo.
echo Done. Updated data\recipes.parquet and data\processed\recipe_annotations.json
