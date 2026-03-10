@echo off
REM Deploy AI News Agent to AWS Lambda via SAM
REM Usage: deploy.bat [stack-name] [region]
REM   stack-name defaults to "ai-news-agent"
REM   region     defaults to "us-east-1"

SET STACK=%1
IF "%STACK%"=="" SET STACK=ai-news-agent

SET REGION=%2
IF "%REGION%"=="" SET REGION=us-east-1

echo.
echo ===================================================
echo  AI News Agent — SAM Deploy
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
sam build --template template.yaml
IF ERRORLEVEL 1 (
    echo ERROR: sam build failed.
    exit /b 1
)

echo.
echo [2/2] Deploying to AWS...
echo       (You will be prompted for API keys and email addresses)
echo.
sam deploy ^
    --stack-name %STACK% ^
    --region %REGION% ^
    --capabilities CAPABILITY_NAMED_IAM ^
    --resolve-s3 ^
    --parameter-overrides ^
        AnthropicApiKey=%ANTHROPIC_API_KEY% ^
        TavilyApiKey=%TAVILY_API_KEY% ^
        EmailTo=%EMAIL_TO% ^
        EmailFrom=%EMAIL_FROM%

IF ERRORLEVEL 1 (
    echo.
    echo ERROR: sam deploy failed.
    echo Check the CloudFormation console for details.
    exit /b 1
)

echo.
echo ===================================================
echo  Deployment complete!
echo  - Lambda runs daily at 03:00 UTC
echo  - Logs: CloudWatch /aws/lambda/ai-news-agent
echo  - Reports: S3 bucket ai-news-agent-reports-^<AccountId^>
echo ===================================================
echo.
echo NOTE: If using SES sandbox mode, verify both EMAIL_FROM
echo       and EMAIL_TO addresses in the AWS SES console.
