# IQ Tracker - Deployment Guide

This guide covers deploying the IQ Tracker application to AWS using Terraform and Docker.

## Architecture Overview

### Production Infrastructure (AWS)

```
┌─────────────────────┐
│   Users (iOS App)   │
└──────────┬──────────┘
           │ HTTPS
           ▼
┌─────────────────────┐
│  Application Load   │
│     Balancer        │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐      ┌──────────────────┐
│   ECS Fargate       │      │  EventBridge     │
│   (Backend API)     │      │  (Scheduler)     │
│   Auto-scaling      │      └────────┬─────────┘
└──────────┬──────────┘               │
           │                          ▼
           │              ┌──────────────────────┐
           │              │   ECS Fargate Task   │
           │              │ (Question Generator) │
           │              └──────────┬───────────┘
           │                         │
           ▼                         ▼
     ┌─────────────────────────────────┐
     │     Amazon RDS PostgreSQL       │
     │    (Multi-AZ for production)    │
     └─────────────────────────────────┘
```

**Components:**
- **ALB**: Routes HTTPS traffic to backend containers
- **ECS Fargate**: Serverless containers for backend API (always running)
- **EventBridge**: Schedules weekly question generation
- **RDS PostgreSQL**: Managed database with automated backups
- **ECR**: Container registry for Docker images
- **CloudWatch**: Logs and monitoring
- **Secrets Manager**: Secure storage for API keys and secrets

## Prerequisites

### Required Tools

1. **AWS CLI** (v2.x)
   ```bash
   # macOS
   brew install awscli

   # Verify installation
   aws --version
   ```

2. **Terraform** (>= 1.0)
   ```bash
   # macOS
   brew install terraform

   # Verify installation
   terraform version
   ```

3. **Docker** (>= 20.x)
   ```bash
   # macOS
   brew install --cask docker

   # Verify installation
   docker --version
   ```

4. **jq** (for JSON parsing in scripts)
   ```bash
   brew install jq
   ```

### AWS Account Setup

1. **Create AWS Account** (if you don't have one)
   - Go to https://aws.amazon.com/
   - Sign up for an account
   - Verify your email and payment method

2. **Create IAM User for Deployment**
   ```bash
   # Create IAM user with admin access (for initial setup)
   aws iam create-user --user-name aiq-deployer

   # Attach AdministratorAccess policy (use more restrictive policy in production)
   aws iam attach-user-policy \
     --user-name aiq-deployer \
     --policy-arn arn:aws:iam::aws:policy/AdministratorAccess

   # Create access keys
   aws iam create-access-key --user-name aiq-deployer
   ```

3. **Configure AWS CLI**
   ```bash
   aws configure
   # Enter your Access Key ID
   # Enter your Secret Access Key
   # Default region: us-east-1
   # Default output format: json
   ```

4. **Verify AWS Configuration**
   ```bash
   aws sts get-caller-identity
   ```

## Initial Deployment

### Step 1: Prepare Configuration

1. **Copy and customize Terraform variables**
   ```bash
   cd deployment/terraform
   cp terraform.tfvars.example terraform.tfvars
   ```

2. **Edit `terraform.tfvars`** with your values:
   ```hcl
   aws_region  = "us-east-1"
   environment = "prod"

   # IMPORTANT: Use strong passwords in production
   db_username = "iqtracker"
   db_password = "YOUR_SECURE_DB_PASSWORD_HERE"
   ```

3. **Generate secure passwords**
   ```bash
   # Generate a secure password for the database
   openssl rand -base64 32
   ```

### Step 2: Set Up Terraform State Backend (Recommended)

For production, use S3 + DynamoDB for Terraform state:

```bash
# Create S3 bucket for state
aws s3api create-bucket \
  --bucket aiq-terraform-state \
  --region us-east-1

# Enable versioning
aws s3api put-bucket-versioning \
  --bucket aiq-terraform-state \
  --versioning-configuration Status=Enabled

# Enable encryption
aws s3api put-bucket-encryption \
  --bucket aiq-terraform-state \
  --server-side-encryption-configuration '{
    "Rules": [{
      "ApplyServerSideEncryptionByDefault": {
        "SSEAlgorithm": "AES256"
      }
    }]
  }'

# Create DynamoDB table for state locking
aws dynamodb create-table \
  --table-name aiq-terraform-locks \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region us-east-1
```

Then uncomment and configure the backend in `main.tf`:
```hcl
backend "s3" {
  bucket         = "aiq-terraform-state"
  key            = "prod/terraform.tfstate"
  region         = "us-east-1"
  dynamodb_table = "aiq-terraform-locks"
  encrypt        = true
}
```

### Step 3: Initialize Terraform

```bash
cd deployment/terraform
terraform init
```

### Step 4: Review Infrastructure Plan

```bash
terraform plan
```

Review the planned changes. You should see:
- VPC with public/private/database subnets
- RDS PostgreSQL instance
- ECR repositories
- ECS cluster and task definitions
- Application Load Balancer
- IAM roles and security groups
- CloudWatch log groups
- EventBridge rule for scheduled tasks

### Step 5: Deploy Infrastructure

```bash
terraform apply
```

Type `yes` when prompted. This will take 10-15 minutes.

**Save the outputs** (displayed at the end):
- `alb_dns_name` - Your API endpoint
- `ecr_backend_repository_url` - Backend container registry
- `ecr_question_service_repository_url` - Question service container registry

### Step 6: Build and Push Docker Images

1. **Authenticate Docker with ECR**
   ```bash
   # Get ECR login credentials
   aws ecr get-login-password --region us-east-1 | \
     docker login --username AWS --password-stdin \
     $(terraform output -raw ecr_backend_repository_url | cut -d'/' -f1)
   ```

2. **Build and push backend image**
   ```bash
   # From repository root
   cd backend

   # Build image
   docker build -t aiq-backend .

   # Tag image
   docker tag aiq-backend:latest \
     $(cd ../deployment/terraform && terraform output -raw ecr_backend_repository_url):latest

   # Push image
   docker push $(cd ../deployment/terraform && terraform output -raw ecr_backend_repository_url):latest
   ```

3. **Build and push question service image**
   ```bash
   # From repository root
   cd question-service

   # Build image
   docker build -t aiq-question-service .

   # Tag image
   docker tag aiq-question-service:latest \
     $(cd ../deployment/terraform && terraform output -raw ecr_question_service_repository_url):latest

   # Push image
   docker push $(cd ../deployment/terraform && terraform output -raw ecr_question_service_repository_url):latest
   ```

### Step 7: Update ECS Service

Force ECS to pull the new images:

```bash
# Update backend service
aws ecs update-service \
  --cluster $(cd deployment/terraform && terraform output -raw ecs_cluster_name) \
  --service $(cd deployment/terraform && terraform output -raw backend_service_name) \
  --force-new-deployment \
  --region us-east-1
```

### Step 8: Run Database Migrations

```bash
# Get the backend task ARN
TASK_ARN=$(aws ecs list-tasks \
  --cluster $(cd deployment/terraform && terraform output -raw ecs_cluster_name) \
  --service-name $(cd deployment/terraform && terraform output -raw backend_service_name) \
  --region us-east-1 \
  --query 'taskArns[0]' \
  --output text)

# Run migrations using ECS Exec (requires enabling ECS Exec on the service)
aws ecs execute-command \
  --cluster $(cd deployment/terraform && terraform output -raw ecs_cluster_name) \
  --task $TASK_ARN \
  --container backend \
  --interactive \
  --command "alembic upgrade head" \
  --region us-east-1
```

Alternatively, run migrations manually:
```bash
# SSH into EC2 bastion host or use AWS Systems Manager Session Manager
# Then connect to the task and run:
# alembic upgrade head
```

### Step 9: Verify Deployment

1. **Check health endpoint**
   ```bash
   ALB_DNS=$(cd deployment/terraform && terraform output -raw alb_dns_name)
   curl http://$ALB_DNS/v1/health

   # Expected response:
   # {"status":"healthy","timestamp":"...","service":"IQ Tracker API","version":"..."}
   ```

2. **Check CloudWatch Logs**
   ```bash
   aws logs tail /ecs/aiq-prod-backend --follow --region us-east-1
   ```

3. **Test API endpoints**
   ```bash
   # Register a user
   curl -X POST http://$ALB_DNS/v1/auth/register \
     -H "Content-Type: application/json" \
     -d '{"email":"test@example.com","password":"TestPassword123!"}'

   # Login
   curl -X POST http://$ALB_DNS/v1/auth/login \
     -H "Content-Type: application/json" \
     -d '{"email":"test@example.com","password":"TestPassword123!"}'
   ```

## Environment Variables and Secrets

### Required Secrets

Add these to AWS Secrets Manager:

```bash
# Create secret for API keys
aws secretsmanager create-secret \
  --name aiq-prod-app-secrets \
  --secret-string '{
    "SECRET_KEY": "your-app-secret-key-here",
    "JWT_SECRET_KEY": "your-jwt-secret-key-here",
    "OPENAI_API_KEY": "your-openai-api-key",
    "ANTHROPIC_API_KEY": "your-anthropic-api-key",
    "GOOGLE_API_KEY": "your-google-api-key"
  }' \
  --region us-east-1
```

Update the ECS task definition to reference these secrets (already configured in Terraform).

## CI/CD Pipeline

### GitHub Actions Workflow

Create `.github/workflows/deploy-prod.yml`:

```yaml
name: Deploy to Production

on:
  push:
    branches: [main]
  workflow_dispatch:

env:
  AWS_REGION: us-east-1
  ECR_BACKEND_REPOSITORY: aiq-backend
  ECR_QUESTION_SERVICE_REPOSITORY: aiq-question-service
  ECS_CLUSTER: aiq-prod-cluster
  ECS_SERVICE: aiq-prod-backend

jobs:
  deploy:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v3

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v2
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: ${{ env.AWS_REGION }}

      - name: Login to Amazon ECR
        id: login-ecr
        uses: aws-actions/amazon-ecr-login@v1

      - name: Build and push backend image
        env:
          ECR_REGISTRY: ${{ steps.login-ecr.outputs.registry }}
          IMAGE_TAG: ${{ github.sha }}
        run: |
          cd backend
          docker build -t $ECR_REGISTRY/$ECR_BACKEND_REPOSITORY:$IMAGE_TAG .
          docker push $ECR_REGISTRY/$ECR_BACKEND_REPOSITORY:$IMAGE_TAG

      - name: Deploy to ECS
        run: |
          aws ecs update-service \
            --cluster $ECS_CLUSTER \
            --service $ECS_SERVICE \
            --force-new-deployment
```

## Monitoring and Logging

### CloudWatch Dashboards

Create a CloudWatch dashboard:

```bash
aws cloudwatch put-dashboard \
  --dashboard-name aiq-prod \
  --dashboard-body file://deployment/monitoring/dashboard.json \
  --region us-east-1
```

### CloudWatch Alarms

Set up alarms for:
- High CPU usage (ECS)
- High memory usage (ECS)
- Database connection errors
- HTTP 5xx errors
- Task failures

### Viewing Logs

```bash
# Backend logs
aws logs tail /ecs/aiq-prod-backend --follow

# Question service logs
aws logs tail /ecs/aiq-prod-question-service --follow

# Database logs
aws rds describe-db-log-files --db-instance-identifier aiq-prod-db
```

## Updating the Application

### Backend Code Changes

```bash
# 1. Make code changes
# 2. Commit and push to main (triggers CI/CD)
# OR manually:

cd backend
docker build -t aiq-backend .

# Tag and push
ECR_URL=$(cd ../deployment/terraform && terraform output -raw ecr_backend_repository_url)
docker tag aiq-backend:latest $ECR_URL:latest
docker push $ECR_URL:latest

# Force ECS to redeploy
aws ecs update-service \
  --cluster aiq-prod-cluster \
  --service aiq-prod-backend \
  --force-new-deployment
```

### Database Migrations

```bash
# Create new migration
cd backend
alembic revision --autogenerate -m "Description of changes"

# Test locally first!
# Then deploy and run:
# (Connect to ECS task as shown in Step 8 above)
alembic upgrade head
```

## Cost Estimation

**Minimum monthly costs (us-east-1):**

- **RDS db.t4g.micro**: ~$15/month (20GB storage)
- **ECS Fargate (1 task, 0.25 vCPU, 0.5GB)**: ~$15/month
- **ALB**: ~$18/month
- **NAT Gateway**: ~$32/month
- **Data transfer**: Variable (~$5-20/month)
- **CloudWatch Logs**: ~$5/month

**Total**: ~$90-100/month for minimal production setup

**Cost optimization tips:**
- Use single NAT gateway (not production recommended)
- Use t4g instances (ARM-based, cheaper)
- Set up CloudWatch log retention (7-30 days)
- Use Fargate Spot for question generation tasks
- Consider Aurora Serverless v2 for database (scales to zero)

## Troubleshooting

### Task failing to start

```bash
# Check task status
aws ecs describe-tasks \
  --cluster aiq-prod-cluster \
  --tasks <task-id> \
  --region us-east-1

# Check stopped tasks
aws ecs list-tasks \
  --cluster aiq-prod-cluster \
  --desired-status STOPPED \
  --region us-east-1
```

### Database connection issues

```bash
# Verify security groups
# Ensure ECS tasks security group can access RDS security group on port 5432

# Test from ECS task
aws ecs execute-command \
  --cluster aiq-prod-cluster \
  --task <task-id> \
  --container backend \
  --interactive \
  --command "pg_isready -h <rds-endpoint> -p 5432"
```

### Image pull errors

```bash
# Verify ECR repository permissions
aws ecr describe-repositories --repository-names aiq-backend

# Re-authenticate Docker
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <ecr-url>
```

## Disaster Recovery

### Database Backups

RDS automated backups are enabled (7-day retention for prod).

To create manual snapshot:
```bash
aws rds create-db-snapshot \
  --db-instance-identifier aiq-prod-db \
  --db-snapshot-identifier aiq-manual-snapshot-$(date +%Y%m%d-%H%M%S)
```

To restore:
```bash
aws rds restore-db-instance-from-db-snapshot \
  --db-instance-identifier aiq-prod-db-restored \
  --db-snapshot-identifier <snapshot-id>
```

### Infrastructure Recovery

All infrastructure is in Terraform. To recreate:
```bash
terraform apply
```

## Tearing Down

To destroy all resources:

```bash
cd deployment/terraform
terraform destroy
```

**WARNING**: This will delete all resources including the database. Create a snapshot first if you need to preserve data.

## Additional Resources

- [AWS ECS Documentation](https://docs.aws.amazon.com/ecs/)
- [Terraform AWS Provider](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
- [FastAPI Deployment](https://fastapi.tiangolo.com/deployment/)
- [Docker Best Practices](https://docs.docker.com/develop/dev-best-practices/)
