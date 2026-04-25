# Plan: CloudFront + Custom Domain for Subscribe Page

## Goal

Replace the raw S3 website URL (`http://ai-news-agent-signup-613261654297.s3-website-us-east-1.amazonaws.com`)
with a friendly HTTPS URL on your own domain — e.g. `https://subscribe.yourdomain.com`.

Architecture: **GoDaddy DNS → CloudFront → S3 static website bucket**

CloudFront adds HTTPS and the custom domain alias. The S3 bucket is unchanged; CloudFront
sits in front of it as a caching reverse proxy.

---

## Files to Modify

- `template.yaml` — add CloudFront distribution + new parameters
- `deploy.bat` — pass new parameters to SAM
- No changes to `signup/handler.py` — CORS origin is already driven by env var

---

## Phase 1: Request an ACM Certificate (manual — AWS Console)

ACM certificates used with CloudFront **must be in `us-east-1`**, regardless of where your
stack is deployed.

### 1a. Open ACM in us-east-1

1. Go to **AWS Console → Certificate Manager**
2. Confirm the region selector (top-right) shows **US East (N. Virginia)**
3. Click **Request a certificate** → **Request a public certificate** → Next

### 1b. Enter your domain

- **Fully qualified domain name:** `subscribe.yourdomain.com`
  (replace with your actual subdomain and domain)
- **Validation method:** DNS validation (recommended)
- Click **Request**

### 1c. Get the DNS validation CNAME from ACM

1. Click into the pending certificate
2. Under **Domains**, find the **CNAME name** and **CNAME value** — they look like:
   ```
   Name:  _abc123def456.subscribe.yourdomain.com
   Value: _xyz789.acm-validations.aws.
   ```
3. Keep this tab open — you will need these values in Phase 2

---

## Phase 2: Add ACM Validation CNAME in GoDaddy (manual)

You must prove to ACM that you own the domain before it issues the certificate.

1. Log in to **GoDaddy → My Products → DNS** (for your domain)
2. Click **Add New Record**
3. Select type **CNAME**
4. Fill in:
   - **Name:** the CNAME name from ACM, **minus** your root domain and the trailing dot.
     For example, if ACM shows `_abc123def456.subscribe.yourdomain.com.`, enter:
     `_abc123def456.subscribe`
   - **Value:** the CNAME value from ACM verbatim (GoDaddy accepts the trailing dot)
   - **TTL:** 1 hour (default is fine)
5. Click **Save**

ACM will poll for this record and issue the certificate within a few minutes (sometimes up
to 30 minutes). Wait until the certificate status shows **Issued** before continuing.

### 1d. Copy the Certificate ARN

Once issued, click the certificate and copy the **ARN** — it looks like:
```
arn:aws:acm:us-east-1:613261654297:certificate/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```
You will paste this into `.env` in Phase 3.

---

## Phase 3: Code Changes

### 3a. `.env` — add two new vars

```
CUSTOM_DOMAIN=subscribe.yourdomain.com
ACM_CERTIFICATE_ARN=arn:aws:acm:us-east-1:613261654297:certificate/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

### 3b. `template.yaml` — add parameters

Add after the existing `ResendAudienceId` parameter:

```yaml
  CustomDomain:
    Type: String
    Description: Custom domain for the signup page (e.g. subscribe.yourdomain.com)

  AcmCertificateArn:
    Type: String
    Description: ARN of ACM certificate for CustomDomain (must be in us-east-1)
```

### 3c. `template.yaml` — update SIGNUP_ALLOWED_ORIGIN

In `SignupFunction` → `Environment` → `Variables`, change:

```yaml
# Before:
SIGNUP_ALLOWED_ORIGIN: !Sub "http://ai-news-agent-signup-${AWS::AccountId}.s3-website-${AWS::Region}.amazonaws.com"

# After:
SIGNUP_ALLOWED_ORIGIN: !Sub "https://${CustomDomain}"
```

### 3d. `template.yaml` — add CloudFront distribution

Add this resource after `SignupBucketPolicy`:

```yaml
  # ── CloudFront distribution for signup page ──────────────────────────────────
  SignupDistribution:
    Type: AWS::CloudFront::Distribution
    Properties:
      DistributionConfig:
        Enabled: true
        DefaultRootObject: subscribe.html
        Aliases:
          - !Ref CustomDomain
        Origins:
          - Id: S3WebsiteOrigin
            DomainName: !Sub "${SignupBucket}.s3-website-${AWS::Region}.amazonaws.com"
            CustomOriginConfig:
              HTTPPort: 80
              OriginProtocolPolicy: http-only
        DefaultCacheBehavior:
          TargetOriginId: S3WebsiteOrigin
          ViewerProtocolPolicy: redirect-to-https
          AllowedMethods:
            - GET
            - HEAD
            - OPTIONS
          CachedMethods:
            - GET
            - HEAD
          ForwardedValues:
            QueryString: false
            Cookies:
              Forward: none
          DefaultTTL: 300
          MaxTTL: 3600
        ViewerCertificate:
          AcmCertificateArn: !Ref AcmCertificateArn
          SslSupportMethod: sni-only
          MinimumProtocolVersion: TLSv1.2_2021
        HttpVersion: http2
```

### 3e. `template.yaml` — update Outputs

Replace the `SignupPageUrl` output value with the CloudFront / custom domain URL:

```yaml
  SignupPageUrl:
    Description: Public signup page URL
    Value: !Sub "https://${CustomDomain}"

  CloudFrontDomain:
    Description: CloudFront distribution domain (use as CNAME target in GoDaddy)
    Value: !GetAtt SignupDistribution.DomainName
```

### 3f. `deploy.bat` — pass new parameters

In the `sam deploy` command, add two more parameter overrides alongside the existing ones:

```bat
CustomDomain=%CUSTOM_DOMAIN% AcmCertificateArn=%ACM_CERTIFICATE_ARN%
```

The full parameter overrides line should look like:

```bat
ParameterOverrides="AnthropicApiKey=%ANTHROPIC_API_KEY% TavilyApiKey=%TAVILY_API_KEY% EmailFrom=%EMAIL_FROM% ResendApiKey=%RESEND_API_KEY% ResendAudienceId=%RESEND_AUDIENCE_ID% CustomDomain=%CUSTOM_DOMAIN% AcmCertificateArn=%ACM_CERTIFICATE_ARN%"
```

Also update the line that reads `.env` to export `CUSTOM_DOMAIN` and `ACM_CERTIFICATE_ARN`
(they must be `set` just like the other vars so `%CUSTOM_DOMAIN%` resolves at deploy time).

---

## Phase 4: Deploy

```bat
cd C:\MyProjects\ai-news-agent
deploy.bat
```

SAM will create the CloudFront distribution. **This takes 10–20 minutes** — CloudFront
propagates globally. Watch the CloudFormation console; the stack will stay in
`UPDATE_IN_PROGRESS` until the distribution is deployed.

When complete, the deploy output will include:

```
CloudFrontDomain   d1234567890abc.cloudfront.net
SignupPageUrl      https://subscribe.yourdomain.com
```

Copy the `CloudFrontDomain` value — you need it for the next step.

---

## Phase 5: Add Subdomain CNAME in GoDaddy (manual)

This is the record that makes `subscribe.yourdomain.com` resolve to CloudFront.

1. Log in to **GoDaddy → My Products → DNS** (for your domain)
2. Click **Add New Record**
3. Select type **CNAME**
4. Fill in:
   - **Name:** `subscribe` (just the subdomain part, not the full domain)
   - **Value:** the `CloudFrontDomain` from the deploy output, e.g. `d1234567890abc.cloudfront.net`
   - **TTL:** 1 hour
5. Click **Save**

DNS propagation typically takes 5–30 minutes. You can check progress with:

```bash
nslookup subscribe.yourdomain.com
```

It should eventually resolve to CloudFront IPs.

---

## Phase 6: Verification

1. Open `https://subscribe.yourdomain.com` in a browser
   - Should load the subscribe page over HTTPS with a valid certificate
   - Padlock icon should show your domain (not cloudfront.net)

2. Submit a test email on the form
   - Should succeed (200) — confirms CORS is working with the new origin

3. Confirm the contact appears in the Resend Audience dashboard

4. Test the unsubscribe page: `https://subscribe.yourdomain.com/unsubscribe.html`

5. Test HTTP redirect: `http://subscribe.yourdomain.com` should redirect to HTTPS
   (CloudFront `redirect-to-https` policy handles this)

6. Verify the old S3 URL still loads the page (it will, but CORS will block form submission
   from it — that is intentional and correct)

---

## Notes

- **Cache invalidation:** After each `deploy.bat` run, CloudFront may serve the old
  `subscribe.html` for up to 5 minutes (DefaultTTL=300). To force immediate refresh after
  a redeploy, run:
  ```bash
  aws cloudfront create-invalidation --distribution-id <ID> --paths "/*"
  ```
  The distribution ID is visible in the CloudFront console or the CloudFormation stack
  resources.

- **Cost:** CloudFront pricing is very low for static pages at this scale — effectively
  free under the AWS free tier (1 TB/month out, 10M requests/month).

- **Certificate renewal:** ACM auto-renews DNS-validated certificates as long as the
  GoDaddy CNAME record remains in place. Do not delete it.
