"""
Email Notification Service for TermiVoxed

Sends transactional emails for:
- Payment receipts
- Subscription confirmations
- Usage alerts
- Password resets
- Account notifications

Uses SendGrid for production, with console fallback for development.
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum

from utils.logger import logger


class EmailType(str, Enum):
    """Types of emails"""
    PAYMENT_RECEIPT = "payment_receipt"
    SUBSCRIPTION_ACTIVATED = "subscription_activated"
    SUBSCRIPTION_RENEWED = "subscription_renewed"
    SUBSCRIPTION_CANCELLED = "subscription_cancelled"
    SUBSCRIPTION_EXPIRING = "subscription_expiring"
    TRIAL_STARTED = "trial_started"
    TRIAL_ENDING = "trial_ending"
    TRIAL_EXPIRED = "trial_expired"
    USAGE_WARNING = "usage_warning"
    USAGE_LIMIT_REACHED = "usage_limit_reached"
    PASSWORD_RESET = "password_reset"
    WELCOME = "welcome"
    ACCOUNT_DEACTIVATED = "account_deactivated"
    DEVICE_LOGIN = "device_login"


@dataclass
class EmailRecipient:
    """Email recipient"""
    email: str
    name: Optional[str] = None


@dataclass
class EmailAttachment:
    """Email attachment"""
    filename: str
    content: bytes
    content_type: str


@dataclass
class Email:
    """Complete email data"""
    to: List[EmailRecipient]
    subject: str
    html_content: str
    plain_content: Optional[str] = None
    from_email: str = "noreply@termivoxed.com"
    from_name: str = "TermiVoxed"
    reply_to: Optional[str] = None
    attachments: Optional[List[EmailAttachment]] = None
    email_type: Optional[EmailType] = None
    metadata: Optional[Dict[str, Any]] = None


class EmailTemplates:
    """HTML email templates"""

    BASE_STYLE = """
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #1a202c;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }
        .header {
            text-align: center;
            padding: 30px 0;
            border-bottom: 3px solid #6b46c1;
        }
        .logo {
            font-size: 28px;
            font-weight: bold;
            color: #6b46c1;
        }
        .content {
            padding: 30px 0;
        }
        .button {
            display: inline-block;
            background: #6b46c1;
            color: white !important;
            padding: 12px 30px;
            text-decoration: none;
            border-radius: 6px;
            font-weight: 600;
            margin: 20px 0;
        }
        .footer {
            text-align: center;
            padding: 20px 0;
            color: #718096;
            font-size: 12px;
            border-top: 1px solid #e2e8f0;
        }
        .highlight {
            background: #f7fafc;
            padding: 20px;
            border-radius: 8px;
            border-left: 4px solid #6b46c1;
            margin: 20px 0;
        }
        .amount {
            font-size: 24px;
            font-weight: bold;
            color: #6b46c1;
        }
    """

    @classmethod
    def _base_template(cls, content: str, title: str = "TermiVoxed") -> str:
        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>{cls.BASE_STYLE}</style>
</head>
<body>
    <div class="header">
        <div class="logo">Termi<span style="color: #9f7aea;">Voxed</span></div>
    </div>
    <div class="content">
        {content}
    </div>
    <div class="footer">
        <p>This email was sent by TermiVoxed. Do not reply to this email.</p>
        <p>Questions? Contact us at support@termivoxed.com</p>
        <p>&copy; {datetime.now().year} LxusBrain. All rights reserved.</p>
    </div>
</body>
</html>
"""

    @classmethod
    def payment_receipt(
        cls,
        customer_name: str,
        amount: str,
        plan_name: str,
        billing_period: str,
        invoice_number: str,
        transaction_id: str,
        next_billing_date: Optional[str] = None
    ) -> str:
        content = f"""
        <h2>Payment Receipt</h2>
        <p>Hi {customer_name},</p>
        <p>Thank you for your payment! Here's your receipt:</p>

        <div class="highlight">
            <p><strong>Plan:</strong> {plan_name} ({billing_period})</p>
            <p><strong>Amount:</strong> <span class="amount">{amount}</span></p>
            <p><strong>Invoice:</strong> {invoice_number}</p>
            <p><strong>Transaction ID:</strong> {transaction_id}</p>
        </div>

        {"<p>Your next billing date is <strong>" + next_billing_date + "</strong>.</p>" if next_billing_date else ""}

        <p>If you have any questions about this charge, please contact our support team.</p>

        <a href="https://app.termivoxed.com/account" class="button">View Account</a>
"""
        return cls._base_template(content, "Payment Receipt - TermiVoxed")

    @classmethod
    def subscription_activated(
        cls,
        customer_name: str,
        plan_name: str,
        features: List[str]
    ) -> str:
        features_html = "".join(f"<li>{feature}</li>" for feature in features)
        content = f"""
        <h2>Subscription Activated!</h2>
        <p>Hi {customer_name},</p>
        <p>Your <strong>{plan_name}</strong> subscription is now active! You have access to:</p>

        <ul style="line-height: 2;">
            {features_html}
        </ul>

        <p>Start creating amazing voice-overs now!</p>

        <a href="https://app.termivoxed.com" class="button">Open TermiVoxed</a>
"""
        return cls._base_template(content, "Subscription Activated - TermiVoxed")

    @classmethod
    def trial_started(cls, customer_name: str, trial_days: int) -> str:
        content = f"""
        <h2>Welcome to TermiVoxed!</h2>
        <p>Hi {customer_name},</p>
        <p>Your <strong>{trial_days}-day free trial</strong> has started! During your trial, you can:</p>

        <ul style="line-height: 2;">
            <li>Create up to 5 exports</li>
            <li>Use all TTS voices</li>
            <li>Generate AI subtitles</li>
            <li>Experience the full editor</li>
        </ul>

        <p>No credit card required. Upgrade anytime to continue using TermiVoxed after your trial.</p>

        <a href="https://app.termivoxed.com" class="button">Start Creating</a>
"""
        return cls._base_template(content, "Welcome to TermiVoxed!")

    @classmethod
    def trial_ending(cls, customer_name: str, days_remaining: int) -> str:
        content = f"""
        <h2>Your Trial is Ending Soon</h2>
        <p>Hi {customer_name},</p>
        <p>Your free trial ends in <strong>{days_remaining} day{'s' if days_remaining > 1 else ''}</strong>.</p>

        <p>Don't lose access to TermiVoxed! Upgrade now to continue creating voice-overs.</p>

        <div class="highlight">
            <p><strong>Individual Plan:</strong> Just ₹149/month ($4.99)</p>
            <p>200 exports, all voices, priority support</p>
        </div>

        <a href="https://app.termivoxed.com/pricing" class="button">View Plans</a>

        <p style="color: #718096; font-size: 14px;">
            If you choose not to upgrade, you'll lose access to export features but can still view your projects.
        </p>
"""
        return cls._base_template(content, "Trial Ending Soon - TermiVoxed")

    @classmethod
    def usage_warning(
        cls,
        customer_name: str,
        usage_type: str,
        current: int,
        limit: int,
        percentage: int
    ) -> str:
        content = f"""
        <h2>Usage Alert</h2>
        <p>Hi {customer_name},</p>
        <p>You've used <strong>{percentage}%</strong> of your monthly {usage_type}.</p>

        <div class="highlight">
            <p><strong>Used:</strong> {current} / {limit}</p>
            <p><strong>Remaining:</strong> {limit - current}</p>
        </div>

        <p>Consider upgrading your plan if you need more {usage_type}.</p>

        <a href="https://app.termivoxed.com/pricing" class="button">Upgrade Plan</a>
"""
        return cls._base_template(content, "Usage Alert - TermiVoxed")

    @classmethod
    def password_reset(cls, customer_name: str, reset_link: str) -> str:
        content = f"""
        <h2>Reset Your Password</h2>
        <p>Hi {customer_name},</p>
        <p>We received a request to reset your password. Click the button below to create a new password:</p>

        <a href="{reset_link}" class="button">Reset Password</a>

        <p style="color: #718096; font-size: 14px;">
            This link will expire in 1 hour. If you didn't request this, you can safely ignore this email.
        </p>
"""
        return cls._base_template(content, "Reset Password - TermiVoxed")

    @classmethod
    def welcome(cls, customer_name: str) -> str:
        content = f"""
        <h2>Welcome to TermiVoxed!</h2>
        <p>Hi {customer_name},</p>
        <p>Thanks for creating an account! You're now ready to create professional voice-overs with AI.</p>

        <h3>Getting Started:</h3>
        <ol style="line-height: 2;">
            <li>Import your video</li>
            <li>Add or generate subtitles</li>
            <li>Choose voices for each language</li>
            <li>Export your dubbed video</li>
        </ol>

        <a href="https://app.termivoxed.com" class="button">Get Started</a>

        <p>Need help? Check out our <a href="https://docs.termivoxed.com">documentation</a> or contact support.</p>
"""
        return cls._base_template(content, "Welcome to TermiVoxed!")


class EmailService:
    """
    Email notification service.

    Uses SendGrid in production, console logging in development.
    """

    def __init__(
        self,
        sendgrid_api_key: Optional[str] = None,
        from_email: str = "noreply@termivoxed.com",
        from_name: str = "TermiVoxed"
    ):
        self.sendgrid_api_key = sendgrid_api_key or os.environ.get("SENDGRID_API_KEY")
        self.from_email = from_email
        self.from_name = from_name
        self.templates = EmailTemplates()

        self._has_sendgrid = self._check_sendgrid()

    def _check_sendgrid(self) -> bool:
        """Check if SendGrid is available and configured"""
        if not self.sendgrid_api_key:
            logger.warning("SendGrid API key not configured, emails will be logged only")
            return False

        try:
            from sendgrid import SendGridAPIClient
            return True
        except ImportError:
            logger.warning("SendGrid not installed, emails will be logged only")
            return False

    async def send(self, email: Email) -> bool:
        """
        Send an email.

        Args:
            email: Email to send

        Returns:
            True if sent successfully
        """
        if self._has_sendgrid and self.sendgrid_api_key:
            return await self._send_sendgrid(email)
        else:
            return self._send_console(email)

    async def _send_sendgrid(self, email: Email) -> bool:
        """Send email via SendGrid"""
        try:
            from sendgrid import SendGridAPIClient
            from sendgrid.helpers.mail import (
                Mail, Email as SGEmail, To, Content, Attachment,
                FileContent, FileName, FileType, Disposition
            )
            import base64

            # Build message
            message = Mail()
            message.from_email = SGEmail(email.from_email, email.from_name)

            for recipient in email.to:
                message.add_to(To(recipient.email, recipient.name))

            message.subject = email.subject
            message.add_content(Content("text/html", email.html_content))

            if email.plain_content:
                message.add_content(Content("text/plain", email.plain_content))

            # Add attachments
            if email.attachments:
                for att in email.attachments:
                    attachment = Attachment()
                    attachment.file_content = FileContent(
                        base64.b64encode(att.content).decode()
                    )
                    attachment.file_name = FileName(att.filename)
                    attachment.file_type = FileType(att.content_type)
                    attachment.disposition = Disposition("attachment")
                    message.add_attachment(attachment)

            # Send
            sg = SendGridAPIClient(self.sendgrid_api_key)
            response = sg.send(message)

            if response.status_code in (200, 201, 202):
                logger.info(f"Email sent to {[r.email for r in email.to]}: {email.subject}")
                return True
            else:
                logger.error(f"SendGrid error: {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False

    def _send_console(self, email: Email) -> bool:
        """Log email to console (development mode)"""
        recipients = ", ".join(r.email for r in email.to)
        logger.info(f"[EMAIL] To: {recipients}")
        logger.info(f"[EMAIL] Subject: {email.subject}")
        logger.info(f"[EMAIL] Type: {email.email_type.value if email.email_type else 'N/A'}")
        logger.debug(f"[EMAIL] Content preview: {email.html_content[:200]}...")
        return True

    # =========================================================================
    # Convenience methods for common emails
    # =========================================================================

    async def send_payment_receipt(
        self,
        to_email: str,
        customer_name: str,
        amount: str,
        plan_name: str,
        billing_period: str,
        invoice_number: str,
        transaction_id: str,
        next_billing_date: Optional[str] = None,
        invoice_pdf: Optional[Path] = None
    ) -> bool:
        """Send payment receipt email"""
        html = self.templates.payment_receipt(
            customer_name, amount, plan_name, billing_period,
            invoice_number, transaction_id, next_billing_date
        )

        attachments = []
        if invoice_pdf and invoice_pdf.exists():
            attachments.append(EmailAttachment(
                filename=invoice_pdf.name,
                content=invoice_pdf.read_bytes(),
                content_type="application/pdf"
            ))

        email = Email(
            to=[EmailRecipient(to_email, customer_name)],
            subject=f"Payment Receipt - {invoice_number}",
            html_content=html,
            attachments=attachments if attachments else None,
            email_type=EmailType.PAYMENT_RECEIPT,
        )

        return await self.send(email)

    async def send_subscription_activated(
        self,
        to_email: str,
        customer_name: str,
        plan_name: str,
        features: List[str]
    ) -> bool:
        """Send subscription activated email"""
        html = self.templates.subscription_activated(customer_name, plan_name, features)

        email = Email(
            to=[EmailRecipient(to_email, customer_name)],
            subject=f"Your {plan_name} Subscription is Active!",
            html_content=html,
            email_type=EmailType.SUBSCRIPTION_ACTIVATED,
        )

        return await self.send(email)

    async def send_trial_started(
        self,
        to_email: str,
        customer_name: str,
        trial_days: int = 7
    ) -> bool:
        """Send trial started email"""
        html = self.templates.trial_started(customer_name, trial_days)

        email = Email(
            to=[EmailRecipient(to_email, customer_name)],
            subject="Welcome to TermiVoxed - Your Free Trial Has Started!",
            html_content=html,
            email_type=EmailType.TRIAL_STARTED,
        )

        return await self.send(email)

    async def send_trial_ending(
        self,
        to_email: str,
        customer_name: str,
        days_remaining: int
    ) -> bool:
        """Send trial ending warning email"""
        html = self.templates.trial_ending(customer_name, days_remaining)

        email = Email(
            to=[EmailRecipient(to_email, customer_name)],
            subject=f"Your Trial Ends in {days_remaining} Day{'s' if days_remaining > 1 else ''}",
            html_content=html,
            email_type=EmailType.TRIAL_ENDING,
        )

        return await self.send(email)

    async def send_usage_warning(
        self,
        to_email: str,
        customer_name: str,
        usage_type: str,
        current: int,
        limit: int
    ) -> bool:
        """Send usage warning email"""
        percentage = int((current / limit) * 100) if limit > 0 else 100
        html = self.templates.usage_warning(
            customer_name, usage_type, current, limit, percentage
        )

        email = Email(
            to=[EmailRecipient(to_email, customer_name)],
            subject=f"Usage Alert: {percentage}% of {usage_type} Used",
            html_content=html,
            email_type=EmailType.USAGE_WARNING,
        )

        return await self.send(email)

    async def send_password_reset(
        self,
        to_email: str,
        customer_name: str,
        reset_link: str
    ) -> bool:
        """Send password reset email"""
        html = self.templates.password_reset(customer_name, reset_link)

        email = Email(
            to=[EmailRecipient(to_email, customer_name)],
            subject="Reset Your TermiVoxed Password",
            html_content=html,
            email_type=EmailType.PASSWORD_RESET,
        )

        return await self.send(email)

    async def send_welcome(
        self,
        to_email: str,
        customer_name: str
    ) -> bool:
        """Send welcome email"""
        html = self.templates.welcome(customer_name)

        email = Email(
            to=[EmailRecipient(to_email, customer_name)],
            subject="Welcome to TermiVoxed!",
            html_content=html,
            email_type=EmailType.WELCOME,
        )

        return await self.send(email)


# Singleton instance
_email_service: Optional[EmailService] = None


def get_email_service(sendgrid_api_key: Optional[str] = None) -> EmailService:
    """Get or create the email service singleton"""
    global _email_service
    if _email_service is None:
        _email_service = EmailService(sendgrid_api_key)
    return _email_service
