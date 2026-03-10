@echo off
echo ========================================================
echo Building AI News Mailing System Executable for Windows
echo ========================================================

echo 1. Installing required packages...
pip install -r requirements.txt
pip install pyinstaller python-dotenv

echo 2. Building the executable...
pyinstaller --noconfirm --onedir --windowed --name "AI_News_Mailing" gui_app.py

echo 3. Creating Output Artifacts Folder...
if not exist "build_output" mkdir "build_output"

echo 4. Copying files to build_output...
copy "dist\AI_News_Mailing\AI_News_Mailing.exe" "build_output\"
copy "dist\AI_News_Mailing\*" "build_output\"

echo 5. Generating Outlook .env Template...
echo SMTP_SERVER=smtp.office365.com > "build_output\.env"
echo SMTP_PORT=587 >> "build_output\.env"
echo SENDER_EMAIL=your_outlook_email@company.com >> "build_output\.env"
echo SENDER_PASSWORD=your_app_password_or_token >> "build_output\.env"
echo RECEIVER_EMAIL=receiver@domain.com >> "build_output\.env"
echo FORWARD_EMAIL=NONE >> "build_output\.env"
echo SCHEDULE_TYPE=once_daily >> "build_output\.env"
echo CAT2_SENDER_EMAIL= >> "build_output\.env"
echo CAT2_SENDER_PASSWORD= >> "build_output\.env"
echo CAT2_RECEIVER_EMAIL= >> "build_output\.env"
echo CAT2_FORWARD_EMAIL=NONE >> "build_output\.env"
echo CAT2_SCHEDULE_TYPE=once_daily >> "build_output\.env"
echo LOG_LEVEL=INFO >> "build_output\.env"

echo Generating README...
echo AI News Mailing Control Panel > "build_output\readme.txt"
echo =============================== >> "build_output\readme.txt"
echo 1. Edit the .env configuration via the GUI or open the .env file in Notepad. >> "build_output\readme.txt"
echo 2. For Outlook/Office 365, ensure SMTP_SERVER is smtp.office365.com and SMTP_PORT is 587. >> "build_output\readme.txt"
echo 3. Click "Run Scheduler" to run the system in the background. >> "build_output\readme.txt"
echo 4. Check the application logs directly from the UI. >> "build_output\readme.txt"

echo Cleaning up pyinstaller temp files...
rmdir /s /q build
rmdir /s /q dist
del AI_News_Mailing.spec

echo ========================================================
echo Build Complete! Check the "build_output" folder.
echo ========================================================
pause
