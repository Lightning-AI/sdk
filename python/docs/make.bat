@ECHO OFF

pushd %~dp0

if "%1" == "" goto help

if "%SPHINXBUILD%" == "" (
	set SPHINXBUILD=sphinx-build
)

for %%R in (sdk cli) do (
	call %%R\make.bat %1
	if errorlevel 1 exit /b 1
)
goto end

:help
echo Build targets: html, linkcheck, clean

:end
popd
