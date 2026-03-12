@echo off
color 0a
setlocal enabledelayedexpansion
git --version >nul 2>&1
if errorlevel 1 (
    echo Git is not installed or not found in PATH. Please install Git and try again.
    pause
    exit /b
) 
:main_menu
cls
set "current_branch="
for /f "tokens=*" %%i in ('git rev-parse --abbrev-ref HEAD 2^>nul') do set "current_branch=%%i"
if "!current_branch!"=="HEAD" (
    set "current_branch=No branch (detached HEAD)"
)
if not defined current_branch (
    set "current_branch=Not a Git repository"
)

echo =============================================================================
echo ^|   Github Commits by The Abyss
echo ^|   Current Branch: !current_branch!
echo ^|   Select options:
echo ^|   1. Create a new Commit
echo ^|   2. View existing Commits
echo ^|   3. Configure Git settings
echo ^|   4. Git Status
echo ^|   5. See Branches available
echo ^|   6. Change Branches / Checkout Branches
echo ^|   7. Exit(add in the end of the program)
echo ^|
echo ^| Note: Make sure Git is installed and configured properly. 
echo ^| If not configured, select option 3 to set up your Git username and email.
echo =============================================================================
set /p option=Enter your choice (1-7):

if "%option%"=="1" (
    call :create_commit
) else if "%option%"=="2" (
    call :view_commits
) else if "%option%"=="3" (
    call :configure_git
) else if "%option%"=="4" (
    call :git_status
) else if "%option%"=="5" (
    call :see_branches
) else if "%option%"=="6" (
    call :change_branches
) else if "%option%"=="7" (
    echo Exiting...
    exit /b
) else (
    echo Invalid option. Please try again.
    pause
    goto :main_menu
)

:create_commit
echo Creating a new commit...
set /p commit_message=Enter your commit message:
git status
git add .
git diff --cached --name-only
git commit -m "%commit_message%"
echo Commit created successfully!
set /p push_now=Do you want to push the commit to the remote repository? (Y/n):
if /i "%push_now%"=="Y" (
    git push
    echo Commit pushed successfully!
) else (
    echo Commit not pushed.
)
pause
goto :main_menu

:view_commits
echo Viewing existing commits...
git log --oneline
pause
goto :main_menu

:configure_git
echo Configuring Git settings...
set /p user_name=Enter your Git username:
set /p user_email=Enter your Git email:
git config --global user.name "%user_name%"
git config --global user.email "%user_email%"
echo Git settings configured successfully!
pause
goto :main_menu

:git_status
echo Checking Git status...
git status
pause
goto :main_menu

:see_branches
echo Seeing available branches...
git branch -a
pause
goto :main_menu

:change_branches
echo Checking Branches...
git branch -a
set /p branch_name=Enter the name of the branch you want to switch to:
git checkout %branch_name%
if  1 (
    echo Failed to switch branches. Please make sure the branch name is correct and try again.
) else (
    echo Switched to branch %branch_name% successfully!
)
set /p new_branch=Do you want to create a new branch from the current branch? (Y/n):
if /i "%new_branch%"=="Y" (
    set /p new_branch_name=Enter the name of the new branch:
    git checkout -b %new_branch_name%
    if errorlevel 1 (
        echo Failed to create and switch to the new branch. Please make sure the branch name is valid and try again.
    ) else (
        echo Created and switched to new branch %new_branch_name% successfully!
    )
)
pause
goto :main_menu