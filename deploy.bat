@echo off
REM Deploy AI News Agent to AWS Lambda via SAM
REM Usage: deploy.bat [stack-name] [region]
REM   stack-name defaults to "ai-news-agent"
REM   region     defaults to "us-east-1"

SET STACK=%1
IF "%STACK%"=="" SET STACK=ai-news-agent

SET REGION=%2
IF "%REGION%"=="" SET REGION=us-east-1

REM Load .env file if present
IF EXIST .env (
    FOR /f "usebackq tokens=1,2 delims==" %%i IN (.env) DO (
        IF NOT "%%i"=="" IF NOT "%%j"=="" SET %%i=%%j
    )
)

echo.
echo ===================================================
echo  AI Learning Digest Agent - SAM Deploy
echo  Stack : %STACK%
echo  Region: %REGION%
echo ===================================================
echo.

REM Check SAM CLI is installed
where sam >nul 2>&1
IF ERRORLEVEL 1 (
    echo ERROR: AWS SAM CLI not found.
    echo Install it from: https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html
    exit /b 1
)

REM Check AWS credentials are configured
aws sts get-caller-identity >nul 2>&1
IF ERRORLEVEL 1 (
    echo ERROR: AWS credentials not configured or expired.
    echo Run: aws configure
    exit /b 1
)

echo [1/2] Building Lambda package...
cmd /c sam build --template template.yaml
SET BUILD_EXIT=%ERRORLEVEL%
IF %BUILD_EXIT% NEQ 0 (
    echo ERROR: sam build failed.
    exit /b 1
)

echo.
echo [2/2] Deploying to AWS...
echo       (You will be prompted for API keys and email addresses)
echo.
cmd /c sam deploy ^
    --stack-name %STACK% ^
    --region %REGION% ^
    --capabilities CAPABILITY_NAMED_IAM ^
    --resolve-s3 ^
    --parameter-overrides ^
        AnthropicApiKey=%ANTHROPIC_API_KEY% ^
        TavilyApiKey=%TAVILY_API_KEY% ^
        EmailFrom=%EMAIL_FROM% ^
        ResendApiKey=%RESEND_API_KEY% ^
        ResendAudienceId=%RESEND_AUDIENCE_ID%

IF ERRORLEVEL 1 (
    echo.
    echo ERROR: sam deploy failed.
    echo Check the CloudFormation console for details.
    exit /b 1
)

echo.
echo [3/3] Uploading signup page to S3...

rem Retrieve AWS account ID
for /f "tokens=*" %%i in ('aws sts get-caller-identity --query "Account" --output text') do set AWS_ACCOUNT_ID=%%i

rem Retrieve SignupApiUrl from stack outputs
for /f "tokens=*" %%i in ('aws cloudformation describe-stacks --stack-name %STACK% --query "Stacks[0].Outputs[?OutputKey=='SignupApiUrl'].OutputValue" --output text') do set SIGNUP_API_URL=%%i

rem Inject API URL into subscribe.html and upload to S3
powershell -Command "(Get-Content signup\subscribe.html) -replace 'SIGNUP_API_URL', '%SIGNUP_API_URL%' | Set-Content signup\subscribe.html.tmp"
aws s3 cp signup\subscribe.html.tmp s3://ai-news-agent-signup-%AWS_ACCOUNT_ID%/subscribe.html --content-type text/html
del signup\subscribe.html.tmp

rem Retrieve UnsubscribeApiUrl from stack outputs
for /f "tokens=*" %%i in ('aws cloudformation describe-stacks --stack-name %STACK% --query "Stacks[0].Outputs[?OutputKey=='UnsubscribeApiUrl'].OutputValue" --output text') do set UNSUBSCRIBE_API_URL=%%i

rem Inject URL into unsubscribe.html and upload to S3
powershell -Command "(Get-Content signup\unsubscribe.html) -replace 'UNSUBSCRIBE_API_URL', '%UNSUBSCRIBE_API_URL%' | Set-Content signup\unsubscribe.html.tmp"
aws s3 cp signup\unsubscribe.html.tmp s3://ai-news-agent-signup-%AWS_ACCOUNT_ID%/unsubscribe.html --content-type text/html
del signup\unsubscribe.html.tmp

rem Retrieve CloudFront URL from stack outputs
for /f "tokens=*" %%i in ('aws cloudformation describe-stacks --stack-name %STACK% --query "Stacks[0].Outputs[?OutputKey=='SignupPageCloudFrontUrl'].OutputValue" --output text') do set SIGNUP_PAGE_CF_URL=%%i

echo.
echo ===================================================
echo  Deployment complete!
echo  - Lambda runs Tue/Fri at 03:00 UTC
echo  - Logs: CloudWatch /aws/lambda/ai-news-agent
echo  - Reports: S3 bucket ai-news-agent-reports-%AWS_ACCOUNT_ID%
echo  - Signup page: %SIGNUP_PAGE_CF_URL%
echo  - Signup API:      %SIGNUP_API_URL%
echo  - Unsubscribe API: %UNSUBSCRIBE_API_URL%
echo ===================================================
echo.
echo NOTE: Ensure EMAIL_FROM is on a Resend-verified domain.
echo NOTE: Ensure RESEND_AUDIENCE_ID is set in .env before deploying.
