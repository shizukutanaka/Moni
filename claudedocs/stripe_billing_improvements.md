# Stripe Billing System - Comprehensive Improvement Analysis

**Date**: 2025-10-08
**Product**: Moni System Monitor
**Current Status**: Basic subscription billing implemented
**Analysis Scope**: Production-ready enterprise billing enhancements

---

## Executive Summary

Moni is a hardened system monitoring solution with enterprise security features. The current Stripe billing implementation provides **basic monthly subscription functionality** with two tiers (Essential and Enterprise). This analysis identifies **13 critical improvements** needed to achieve production-grade billing suitable for SaaS operations.

### Current Implementation Status

✅ **Implemented**:
- Stripe Checkout integration
- Webhook event handling (created/updated/deleted)
- Basic subscription status tracking
- Customer portal access
- Tier-based pricing configuration
- Trial period support

❌ **Missing Critical Features**:
- Usage-based metering
- Plan change workflows (upgrade/downgrade)
- Proration handling
- Payment failure recovery
- Dunning management
- Tax calculation
- Analytics and reporting
- Customer-facing UI components
- Comprehensive test coverage

---

## Product Analysis

### Product Type
**B2B SaaS Monitoring Tool** with security/compliance focus

### Target Market
- System administrators
- IT departments
- Enterprise security teams
- Government/regulated industries (FIPS 140-2, ISO 27001)

### Value Proposition
Real-time system monitoring with enterprise security controls, RBAC, encryption, and compliance frameworks.

### Optimal Billing Model

**Recommended**: **Hybrid Subscription + Usage-Based Metering**

#### Rationale:
1. **Base Subscription** - Predictable revenue for core monitoring features
2. **Usage Metering** - Scalable pricing for:
   - Number of monitored endpoints/servers
   - Data retention period (metrics history)
   - Alert volume
   - Export frequency
   - Advanced security scans

#### Pricing Tiers (Recommended Structure):

**Essential Tier** ($29/month)
- Single endpoint monitoring
- 7-day metrics retention
- Basic dashboards
- 100 alerts/month
- Community support

**Professional Tier** ($99/month)
- Up to 10 endpoints
- 30-day retention
- Advanced metrics + RBAC
- 1,000 alerts/month
- Email support
- Compliance exports

**Enterprise Tier** ($299/month + usage)
- Unlimited endpoints (metered at $10/endpoint)
- 90-day retention (extendable to 1 year at $50/month)
- Full security suite (IDS, encryption, 2FA)
- Unlimited alerts
- Priority support + SLA
- Audit logging + compliance packages

**Usage-Based Add-Ons**:
- Additional endpoints: $10/endpoint/month
- Extended retention: $50/month per 90 days
- Advanced security scans: $0.10 per scan
- API calls: $1 per 10,000 requests

---

## Critical Improvements Required

### 1. Usage-Based Metering Infrastructure

**Priority**: HIGH
**Complexity**: HIGH
**Impact**: Revenue optimization, scalable pricing

#### Current Gap
Only subscription billing exists. No usage tracking or metered billing.

#### Implementation Requirements

**Metering Service** (`src/moni/billing/metering.py`):
```python
- Track endpoint count per customer
- Monitor data retention consumption
- Count alert volume
- Track API requests
- Export usage events to Stripe
```

**Stripe Integration**:
- Create metered price IDs for add-ons
- Report usage via `stripe.SubscriptionItem.create_usage_record()`
- Implement usage aggregation (sum/max/last_during_period)
- Handle metering edge cases (negative usage, resets)

**Database Schema**:
```sql
CREATE TABLE usage_events (
    id SERIAL PRIMARY KEY,
    customer_id VARCHAR(255) NOT NULL,
    metric_name VARCHAR(100) NOT NULL,
    quantity INTEGER NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    reported_to_stripe BOOLEAN DEFAULT FALSE,
    stripe_usage_record_id VARCHAR(255)
);
```

**Key Files to Create**:
- `src/moni/billing/metering.py` - Usage tracking service
- `src/moni/billing/usage_reporter.py` - Stripe usage reporter
- `src/moni/billing/quota_enforcer.py` - Enforce tier limits

---

### 2. Subscription Upgrade/Downgrade Flow

**Priority**: HIGH
**Complexity**: MEDIUM
**Impact**: Customer retention, flexibility

#### Current Gap
No plan change functionality. Customers must cancel and re-subscribe.

#### Implementation Requirements

**API Endpoints** (add to `billing_api.py`):
```python
POST /subscription/{customer_id}/upgrade
POST /subscription/{customer_id}/downgrade
POST /subscription/{customer_id}/change-plan
```

**Service Methods** (`billing/service.py`):
```python
def upgrade_subscription(customer_id: str, new_price_id: str, prorate: bool = True)
def downgrade_subscription(customer_id: str, new_price_id: str, at_period_end: bool = True)
def preview_plan_change(customer_id: str, new_price_id: str) -> ProrationPreview
```

**Business Logic**:
- Upgrades: Apply immediately with proration
- Downgrades: Schedule for end of billing period (avoid refunds)
- Preview invoice before change
- Validate tier eligibility
- Handle usage-based add-ons during transitions

---

### 3. Proration Handling

**Priority**: HIGH
**Complexity**: MEDIUM
**Impact**: Revenue accuracy, customer trust

#### Current Gap
No proration logic for mid-cycle plan changes.

#### Implementation Requirements

**Proration Modes**:
1. **Upgrade**: Charge prorated difference immediately
2. **Downgrade**: Credit applied to next invoice
3. **Add-ons**: Prorated for current period

**Stripe Configuration**:
```python
stripe.Subscription.modify(
    subscription_id,
    proration_behavior='create_prorations',  # or 'always_invoice', 'none'
    items=[{
        'id': subscription_item_id,
        'price': new_price_id,
    }],
)
```

**Preview Invoice**:
```python
def preview_subscription_change(customer_id: str, new_price_id: str) -> InvoicePreview:
    upcoming_invoice = stripe.Invoice.upcoming(
        customer=customer_id,
        subscription=subscription_id,
        subscription_items=[{'id': item_id, 'price': new_price_id}],
    )
    return {
        'immediate_charge': upcoming_invoice.amount_due,
        'proration_amount': sum(line.amount for line in upcoming_invoice.lines if line.proration),
        'next_invoice_date': upcoming_invoice.period_end,
    }
```

---

### 4. Enhanced Webhook Event Handling

**Priority**: CRITICAL
**Complexity**: MEDIUM
**Impact**: Data consistency, reliability

#### Current Gap
Basic webhook handling exists but lacks:
- Event logging
- Retry logic
- Idempotency guarantees
- Comprehensive event coverage

#### Implementation Requirements

**Event Types to Add**:
```python
# Current: created, updated, deleted
# Add these:
- customer.subscription.trial_will_end (3 days before)
- customer.subscription.paused
- customer.subscription.resumed
- invoice.upcoming (7 days before renewal)
- invoice.payment_action_required (3DS authentication)
- payment_intent.succeeded
- payment_intent.payment_failed
- customer.deleted
```

**Webhook Event Logger** (`billing/webhook_logger.py`):
```python
CREATE TABLE webhook_events (
    id SERIAL PRIMARY KEY,
    event_id VARCHAR(255) UNIQUE NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    received_at TIMESTAMP DEFAULT NOW(),
    processed BOOLEAN DEFAULT FALSE,
    retry_count INTEGER DEFAULT 0,
    payload JSONB,
    error_message TEXT
);
```

**Idempotency**:
```python
def handle_event(event: stripe.Event) -> None:
    if is_event_processed(event.id):
        logger.info(f"Duplicate event {event.id}, skipping")
        return

    try:
        mark_event_processing(event.id)
        # Process event
        mark_event_processed(event.id)
    except Exception as e:
        mark_event_failed(event.id, str(e))
        raise
```

---

### 5. Payment Failure Recovery

**Priority**: CRITICAL
**Complexity**: HIGH
**Impact**: Revenue retention, churn reduction

#### Current Gap
No automated payment recovery workflows.

#### Implementation Requirements

**Smart Retries**:
- Stripe automatic retries (configurable schedule)
- Email notifications to customers
- Grace period before service suspension
- Automatic reactivation on successful payment

**Webhook Handlers**:
```python
def handle_payment_failed(event):
    invoice = event.data.object
    customer = invoice.customer

    # Send notification
    notify_customer_payment_failed(customer, invoice)

    # Apply grace period
    set_subscription_grace_period(customer, days=7)

    # Schedule retry
    schedule_payment_retry(invoice, retry_schedule=[3, 7, 14])

def handle_payment_succeeded_after_failure(event):
    # Restore full access
    reactivate_subscription(customer_id)
    send_reactivation_email(customer)
```

**Grace Period Management**:
```python
@dataclass
class SubscriptionRecord:
    # Add fields:
    payment_failed_at: Optional[datetime] = None
    grace_period_ends: Optional[datetime] = None

    @property
    def in_grace_period(self) -> bool:
        if not self.grace_period_ends:
            return False
        return datetime.now(tz=timezone.utc) < self.grace_period_ends
```

---

### 6. Dunning Management

**Priority**: HIGH
**Complexity**: MEDIUM
**Impact**: Churn reduction, revenue recovery

#### Current Gap
No automated email sequences for failed payments.

#### Implementation Requirements

**Dunning Workflow**:
1. **Day 0** (Payment fails): "Payment failed, please update card"
2. **Day 3**: "Retry scheduled, update card to avoid suspension"
3. **Day 7**: "Final notice - service suspended in 24 hours"
4. **Day 8**: Suspend service (retain data)
5. **Day 30**: Cancel subscription + delete data

**Email Templates** (`src/moni/billing/email_templates.py`):
```python
PAYMENT_FAILED_INITIAL = """
Subject: Payment Failed - Action Required

Your recent payment of {amount} failed. Please update your payment method
within 7 days to avoid service interruption.

[Update Payment Method] (link to billing portal)
"""

GRACE_PERIOD_ENDING = """
Subject: Final Notice - Service Suspension Tomorrow

Your Moni subscription will be suspended in 24 hours due to failed payment.
Update your payment method now to maintain access.
"""
```

**Service Suspension Logic**:
```python
def suspend_subscription(customer_id: str):
    # Disable monitoring access
    # Retain configuration data
    # Send suspension email
    # Schedule cancellation in 30 days
```

---

### 7. Tax Calculation Integration

**Priority**: MEDIUM
**Complexity**: HIGH
**Impact**: Compliance, international sales

#### Current Gap
No tax calculation for VAT, GST, sales tax.

#### Implementation Requirements

**Stripe Tax**:
```python
# Enable automatic tax calculation
stripe.checkout.Session.create(
    automatic_tax={'enabled': True},
    customer_update={'address': 'auto'},
    # ...
)

# Sync tax IDs
stripe.Customer.modify(
    customer_id,
    tax_id_data=[{
        'type': 'eu_vat',
        'value': 'DE123456789',
    }]
)
```

**Tax Configuration**:
```python
# Environment variables
MONI_STRIPE_TAX_ENABLED=true
MONI_STRIPE_TAX_CODE=txcd_10000000  # Software as a Service

# Tax-inclusive pricing toggle
MONI_STRIPE_PRICES_INCLUDE_TAX=false
```

**Invoice Display**:
```python
{
    "subtotal": 99.00,
    "tax": 19.80,  # 20% VAT
    "total": 118.80,
    "tax_breakdown": [
        {"jurisdiction": "EU", "rate": 0.20, "amount": 19.80}
    ]
}
```

---

### 8. Customer Dashboard UI

**Priority**: HIGH
**Complexity**: MEDIUM
**Impact**: User experience, self-service

#### Current Gap
No customer-facing billing UI in the application.

#### Implementation Requirements

**UI Components** (`src/moni/ui/billing/`):

**BillingDashboard.py**:
```python
class BillingDashboard(QWidget):
    - Display current subscription tier
    - Show next billing date
    - Usage meter (endpoints, retention, alerts)
    - Upgrade/downgrade buttons
    - Access billing portal
    - Download invoices
```

**SubscriptionCard.py**:
```python
class SubscriptionCard(QWidget):
    - Tier name + features
    - Billing amount + interval
    - Trial/grace period status
    - Renewal date countdown
    - Cancel/pause options
```

**UsageMetrics.py**:
```python
class UsageMetrics(QWidget):
    - Endpoint count (5/10 used)
    - Storage usage (23 GB / 100 GB)
    - Alert quota (456 / 1,000)
    - Progress bars with warnings
```

**Integration**:
```python
# Add to main application
from moni.ui.billing import BillingDashboard

class MoniApplication:
    def show_billing_dashboard(self):
        dashboard = BillingDashboard(self.customer_id)
        dashboard.show()
```

---

### 9. Billing Analytics & Reporting

**Priority**: MEDIUM
**Complexity**: MEDIUM
**Impact**: Business intelligence, revenue insights

#### Current Gap
No analytics for subscription metrics.

#### Implementation Requirements

**Metrics to Track**:
- Monthly Recurring Revenue (MRR)
- Annual Recurring Revenue (ARR)
- Customer Lifetime Value (LTV)
- Churn rate
- Upgrade/downgrade rates
- Trial conversion rate
- Payment failure rate
- Average revenue per user (ARPU)

**Analytics Service** (`billing/analytics.py`):
```python
class BillingAnalytics:
    def calculate_mrr(self) -> Decimal
    def calculate_churn_rate(self, period_days: int = 30) -> float
    def get_trial_conversion_rate(self) -> float
    def get_revenue_by_tier(self) -> Dict[str, Decimal]
    def get_payment_health_metrics(self) -> PaymentHealthReport
```

**Admin Dashboard** (`billing_api.py`):
```python
@app.get("/admin/analytics")
def get_billing_analytics(
    admin_key: str = Header(..., alias="X-Admin-Key")
) -> BillingAnalyticsResponse:
    validate_admin_key(admin_key)
    return {
        'mrr': analytics.calculate_mrr(),
        'active_subscriptions': count_active_subscriptions(),
        'churn_rate': analytics.calculate_churn_rate(),
        'tier_distribution': analytics.get_revenue_by_tier(),
    }
```

---

### 10. Enhanced Tier Configuration

**Priority**: MEDIUM
**Complexity**: LOW
**Impact**: Flexibility, feature gating

#### Current Gap
Tier configuration is environment-variable based with limited metadata.

#### Implementation Requirements

**Tier Configuration File** (`configs/billing_tiers.yaml`):
```yaml
tiers:
  essential:
    name: Essential
    stripe_price_id: price_essential_monthly
    description: Core monitoring for single endpoints
    billing_interval: month
    trial_period_days: 0
    base_price: 29.00
    features:
      - id: endpoints
        limit: 1
        metered: false
      - id: retention_days
        limit: 7
        metered: false
      - id: alerts_per_month
        limit: 100
        metered: true
      - id: rbac
        enabled: false
      - id: compliance_exports
        enabled: false

  enterprise:
    name: Enterprise
    stripe_price_id: price_enterprise_monthly
    description: Full security suite with unlimited scale
    billing_interval: month
    trial_period_days: 14
    base_price: 299.00
    features:
      - id: endpoints
        limit: null  # unlimited base, metered beyond
        metered: true
        unit_price: 10.00
      - id: retention_days
        limit: 90
        metered: true
        unit_price: 50.00  # per 90 days
      - id: rbac
        enabled: true
      - id: compliance_exports
        enabled: true
      - id: intrusion_detection
        enabled: true
```

**Feature Flag Enforcement** (`billing/feature_flags.py`):
```python
class FeatureGate:
    def __init__(self, customer_id: str):
        self.subscription = get_by_customer(customer_id)
        self.tier_config = load_tier_config(self.subscription.tier_name)

    def can_add_endpoint(self) -> bool:
        current_count = count_customer_endpoints(self.customer_id)
        limit = self.tier_config.features['endpoints'].limit
        return limit is None or current_count < limit

    def has_feature(self, feature_id: str) -> bool:
        return self.tier_config.features[feature_id].enabled
```

---

### 11. Subscription Pause/Resume

**Priority**: LOW
**Complexity**: LOW
**Impact**: Customer flexibility

#### Implementation Requirements

**API Endpoints**:
```python
@app.post("/subscription/{customer_id}/pause")
def pause_subscription(customer_id: str, payload: Dict[str, Any]):
    resumes_at = payload.get('resumes_at')  # Optional date
    service.pause_subscription(customer_id, resumes_at)

@app.post("/subscription/{customer_id}/resume")
def resume_subscription(customer_id: str):
    service.resume_subscription(customer_id)
```

**Stripe Integration**:
```python
def pause_subscription(customer_id: str, resumes_at: datetime | None = None):
    subscription = get_subscription(customer_id)
    stripe.Subscription.modify(
        subscription.subscription_id,
        pause_collection={
            'behavior': 'mark_uncollectible',
            'resumes_at': int(resumes_at.timestamp()) if resumes_at else None,
        }
    )
```

---

### 12. Invoice Management

**Priority**: MEDIUM
**Complexity**: LOW
**Impact**: Customer self-service

#### Implementation Requirements

**API Endpoints**:
```python
@app.get("/invoices/{customer_id}")
def list_invoices(customer_id: str, limit: int = 10):
    invoices = stripe.Invoice.list(customer=customer_id, limit=limit)
    return [serialize_invoice(inv) for inv in invoices.data]

@app.get("/invoice/{invoice_id}/pdf")
def download_invoice_pdf(invoice_id: str):
    invoice = stripe.Invoice.retrieve(invoice_id)
    return redirect(invoice.invoice_pdf)
```

**UI Integration**:
- Display invoice history in billing dashboard
- Download PDF button
- Email invoice to customer
- Show payment status (paid/unpaid/void)

---

### 13. Comprehensive Testing

**Priority**: CRITICAL
**Complexity**: HIGH
**Impact**: Reliability, confidence

#### Current Gap
No billing-specific tests exist.

#### Test Coverage Required

**Unit Tests** (`tests/billing/`):
```python
test_billing_service.py:
- test_create_checkout_session
- test_retrieve_subscription
- test_upgrade_subscription
- test_downgrade_subscription
- test_proration_calculation

test_webhooks.py:
- test_subscription_created
- test_subscription_updated
- test_subscription_deleted
- test_payment_failed
- test_invoice_paid
- test_idempotency

test_metering.py:
- test_usage_tracking
- test_stripe_reporting
- test_quota_enforcement
- test_overage_calculation
```

**Integration Tests**:
```python
test_billing_flow.py:
- test_complete_checkout_flow
- test_subscription_lifecycle
- test_plan_upgrade_flow
- test_payment_failure_recovery
- test_webhook_processing
```

**Stripe Test Mode**:
```python
# Use test API keys
MONI_STRIPE_SECRET_KEY=sk_test_...

# Test cards
4242424242424242  # Success
4000000000000002  # Decline
4000002500003155  # 3DS required
```

---

## Implementation Roadmap

### Phase 1: Critical Foundation (Week 1-2)
1. Enhanced webhook handling + logging
2. Payment failure recovery
3. Comprehensive test suite
4. Database schema for events/usage

### Phase 2: Core Features (Week 3-4)
5. Usage-based metering infrastructure
6. Subscription upgrade/downgrade flow
7. Proration handling
8. Customer dashboard UI

### Phase 3: Advanced Features (Week 5-6)
9. Dunning management
10. Tax calculation integration
11. Enhanced tier configuration
12. Billing analytics

### Phase 4: Polish & Scale (Week 7-8)
13. Invoice management
14. Subscription pause/resume
15. Admin dashboard
16. Performance optimization

---

## Database Schema Updates

```sql
-- Webhook event log
CREATE TABLE webhook_events (
    id SERIAL PRIMARY KEY,
    event_id VARCHAR(255) UNIQUE NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    received_at TIMESTAMP DEFAULT NOW(),
    processed BOOLEAN DEFAULT FALSE,
    retry_count INTEGER DEFAULT 0,
    payload JSONB,
    error_message TEXT,
    INDEX idx_event_type (event_type),
    INDEX idx_processed (processed)
);

-- Usage tracking
CREATE TABLE usage_events (
    id SERIAL PRIMARY KEY,
    customer_id VARCHAR(255) NOT NULL,
    subscription_id VARCHAR(255),
    metric_name VARCHAR(100) NOT NULL,
    quantity DECIMAL(10,2) NOT NULL,
    timestamp TIMESTAMP DEFAULT NOW(),
    reported_to_stripe BOOLEAN DEFAULT FALSE,
    stripe_usage_record_id VARCHAR(255),
    INDEX idx_customer_metric (customer_id, metric_name),
    INDEX idx_reported (reported_to_stripe)
);

-- Subscription history
CREATE TABLE subscription_history (
    id SERIAL PRIMARY KEY,
    customer_id VARCHAR(255) NOT NULL,
    subscription_id VARCHAR(255) NOT NULL,
    event_type VARCHAR(50) NOT NULL,  -- created, upgraded, downgraded, canceled
    old_price_id VARCHAR(255),
    new_price_id VARCHAR(255),
    timestamp TIMESTAMP DEFAULT NOW(),
    metadata JSONB
);

-- Payment failures
CREATE TABLE payment_failures (
    id SERIAL PRIMARY KEY,
    customer_id VARCHAR(255) NOT NULL,
    invoice_id VARCHAR(255) NOT NULL,
    failed_at TIMESTAMP DEFAULT NOW(),
    failure_code VARCHAR(100),
    failure_message TEXT,
    retry_count INTEGER DEFAULT 0,
    next_retry_at TIMESTAMP,
    resolved BOOLEAN DEFAULT FALSE,
    resolved_at TIMESTAMP
);
```

---

## Configuration Updates

### Environment Variables to Add

```bash
# Metering
MONI_STRIPE_METERING_ENABLED=true
MONI_STRIPE_USAGE_REPORTING_INTERVAL_HOURS=24

# Tax
MONI_STRIPE_TAX_ENABLED=true
MONI_STRIPE_TAX_CODE=txcd_10000000
MONI_STRIPE_PRICES_INCLUDE_TAX=false

# Payment Recovery
MONI_STRIPE_GRACE_PERIOD_DAYS=7
MONI_STRIPE_RETRY_SCHEDULE=3,7,14
MONI_STRIPE_SUSPENSION_DELAY_DAYS=8

# Dunning
MONI_STRIPE_DUNNING_ENABLED=true
MONI_STRIPE_DUNNING_EMAIL_FROM=billing@moni.example.com

# Analytics
MONI_STRIPE_ANALYTICS_ADMIN_KEY=admin_secret_key_here

# Database (for production)
MONI_BILLING_DB_URL=postgresql://user:pass@localhost/moni_billing
```

---

## API Documentation Updates

### New Endpoints

```
POST   /subscription/{customer_id}/upgrade
POST   /subscription/{customer_id}/downgrade
POST   /subscription/{customer_id}/pause
POST   /subscription/{customer_id}/resume
GET    /subscription/{customer_id}/preview-change
GET    /subscription/{customer_id}/usage
GET    /invoices/{customer_id}
GET    /invoice/{invoice_id}/pdf
POST   /usage/report
GET    /admin/analytics
GET    /admin/customers
GET    /admin/failed-payments
```

---

## Security Considerations

1. **Webhook Signature Verification**: Already implemented ✅
2. **Admin API Protection**: Add API key authentication
3. **Customer Data Isolation**: Validate customer_id ownership
4. **Rate Limiting**: Prevent billing API abuse
5. **PCI Compliance**: Never store card data (Stripe handles)
6. **Audit Logging**: Log all billing operations

---

## Migration Strategy

### For Existing Customers

1. **No Breaking Changes**: Current subscriptions continue unaffected
2. **Opt-In Metering**: Enable usage-based pricing for new signups only
3. **Grandfather Pricing**: Existing customers keep current rates
4. **Communication**: Email notification 30 days before any changes

### Rollout Plan

1. Deploy to staging environment
2. Test with Stripe test mode
3. Migrate 10% of customers (pilot group)
4. Monitor for 1 week
5. Gradual rollout to 100%

---

## Success Metrics

**Technical KPIs**:
- Webhook processing success rate > 99.9%
- Payment retry recovery rate > 40%
- API response time < 200ms (p95)
- Zero revenue leakage from metering

**Business KPIs**:
- Trial-to-paid conversion rate > 25%
- Monthly churn rate < 5%
- Upgrade rate > 10% per quarter
- Customer lifetime value > $1,200

---

## Conclusion

The current Moni billing implementation provides a **solid foundation** with Stripe Checkout, webhooks, and basic subscription management. However, **13 critical enhancements** are required for production-grade SaaS billing:

**Must-Have (P0)**:
1. Usage-based metering
2. Payment failure recovery
3. Enhanced webhook handling
4. Comprehensive testing

**Should-Have (P1)**:
5. Upgrade/downgrade flows
6. Dunning management
7. Customer dashboard UI
8. Billing analytics

**Nice-to-Have (P2)**:
9. Tax calculation
10. Enhanced tier config
11. Invoice management
12. Subscription pause

**Estimated Effort**: 6-8 weeks for full implementation
**Recommended Approach**: Phased rollout starting with critical foundation

This analysis provides a complete roadmap to transform Moni's billing from basic subscription support to enterprise-grade revenue infrastructure.
