"""
Invoice PDF Generator for TermiVoxed

Generates professional PDF invoices for subscription payments.
Supports multi-currency (INR/USD) and GST compliance for India.
"""

import io
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum

from utils.logger import logger


class InvoiceStatus(str, Enum):
    """Invoice status"""
    DRAFT = "draft"
    ISSUED = "issued"
    PAID = "paid"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


@dataclass
class InvoiceLineItem:
    """Line item in an invoice"""
    description: str
    quantity: int
    unit_price: float
    tax_rate: float  # Percentage (e.g., 18 for 18% GST)
    currency: str

    @property
    def subtotal(self) -> float:
        return self.quantity * self.unit_price

    @property
    def tax_amount(self) -> float:
        return self.subtotal * (self.tax_rate / 100)

    @property
    def total(self) -> float:
        return self.subtotal + self.tax_amount


@dataclass
class InvoiceAddress:
    """Address for invoice"""
    name: str
    address_line1: str
    address_line2: Optional[str] = None
    city: str = ""
    state: str = ""
    postal_code: str = ""
    country: str = ""
    email: Optional[str] = None
    phone: Optional[str] = None
    gstin: Optional[str] = None  # For Indian GST


@dataclass
class Invoice:
    """Complete invoice data"""
    invoice_number: str
    invoice_date: datetime
    due_date: datetime
    status: InvoiceStatus

    # Parties
    from_address: InvoiceAddress
    to_address: InvoiceAddress

    # Items
    line_items: List[InvoiceLineItem]

    # Currency
    currency: str
    currency_symbol: str

    # Payment info
    payment_method: str
    transaction_id: Optional[str] = None
    paid_date: Optional[datetime] = None

    # Notes
    notes: Optional[str] = None
    terms: Optional[str] = None

    @property
    def subtotal(self) -> float:
        return sum(item.subtotal for item in self.line_items)

    @property
    def total_tax(self) -> float:
        return sum(item.tax_amount for item in self.line_items)

    @property
    def total(self) -> float:
        return sum(item.total for item in self.line_items)


class InvoicePDFGenerator:
    """
    Generates PDF invoices using reportlab.

    Falls back to HTML template if reportlab is not available.

    Company details are configured via environment variables:
    - TERMIVOXED_COMPANY_NAME: Legal company name (default: LXUSBrain Technologies)
    - TERMIVOXED_COMPANY_ADDRESS: Street address
    - TERMIVOXED_COMPANY_CITY: City
    - TERMIVOXED_COMPANY_STATE: State
    - TERMIVOXED_COMPANY_POSTAL: Postal code
    - TERMIVOXED_COMPANY_COUNTRY: Country (default: India)
    - TERMIVOXED_BILLING_EMAIL: Billing email (default: billing@termivoxed.com)
    - TERMIVOXED_GSTIN: GST Identification Number (optional, for Indian businesses with >20L turnover)
    """

    # Company details from environment (with sensible defaults)
    COMPANY_NAME = "TermiVoxed"
    COMPANY_LEGAL_NAME = os.getenv("TERMIVOXED_COMPANY_NAME", "LXUSBrain Technologies")

    @classmethod
    def get_company_address(cls) -> InvoiceAddress:
        """Get company address from environment variables."""
        gstin = os.getenv("TERMIVOXED_GSTIN", "").strip()

        return InvoiceAddress(
            name=cls.COMPANY_LEGAL_NAME,
            address_line1=os.getenv("TERMIVOXED_COMPANY_ADDRESS", ""),
            city=os.getenv("TERMIVOXED_COMPANY_CITY", ""),
            state=os.getenv("TERMIVOXED_COMPANY_STATE", ""),
            postal_code=os.getenv("TERMIVOXED_COMPANY_POSTAL", ""),
            country=os.getenv("TERMIVOXED_COMPANY_COUNTRY", "India"),
            email=os.getenv("TERMIVOXED_BILLING_EMAIL", "billing@termivoxed.com"),
            # GSTIN is optional - only required for Indian businesses with turnover > 20 lakhs INR
            # Leave empty until you register for GST
            gstin=gstin if gstin else None,
        )

    # Legacy class attribute for backwards compatibility
    COMPANY_ADDRESS = None  # Will be populated in __init__

    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or Path("storage/invoices")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Initialize company address from environment
        self.company_address = self.get_company_address()

        # Check if reportlab is available
        self._has_reportlab = self._check_reportlab()

    def _check_reportlab(self) -> bool:
        """Check if reportlab is available"""
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.units import inch
            return True
        except ImportError:
            logger.warning("reportlab not installed, PDF generation will use HTML fallback")
            return False

    def generate_invoice(
        self,
        invoice: Invoice,
        filename: Optional[str] = None
    ) -> Path:
        """
        Generate a PDF invoice.

        Args:
            invoice: Invoice data
            filename: Optional custom filename

        Returns:
            Path to generated PDF file
        """
        if not filename:
            filename = f"invoice_{invoice.invoice_number}.pdf"

        output_path = self.output_dir / filename

        if self._has_reportlab:
            self._generate_pdf_reportlab(invoice, output_path)
        else:
            # Fallback to HTML
            html_path = output_path.with_suffix('.html')
            self._generate_html(invoice, html_path)
            output_path = html_path

        logger.info(f"Invoice generated: {output_path}")
        return output_path

    def _generate_pdf_reportlab(self, invoice: Invoice, output_path: Path) -> None:
        """Generate PDF using reportlab"""
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import inch, cm
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
        )
        from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER

        # Create document
        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=A4,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72
        )

        # Styles
        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(
            name='InvoiceTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#6b46c1'),  # Purple
            spaceAfter=30,
        ))
        styles.add(ParagraphStyle(
            name='SectionTitle',
            parent=styles['Heading2'],
            fontSize=12,
            textColor=colors.HexColor('#4a5568'),
            spaceAfter=10,
        ))
        styles.add(ParagraphStyle(
            name='Normal_Right',
            parent=styles['Normal'],
            alignment=TA_RIGHT,
        ))

        # Build content
        content = []

        # Header with invoice title and number
        content.append(Paragraph("INVOICE", styles['InvoiceTitle']))

        # Invoice details table
        invoice_details = [
            ['Invoice Number:', invoice.invoice_number],
            ['Date:', invoice.invoice_date.strftime('%B %d, %Y')],
            ['Due Date:', invoice.due_date.strftime('%B %d, %Y')],
            ['Status:', invoice.status.value.upper()],
        ]

        if invoice.transaction_id:
            invoice_details.append(['Transaction ID:', invoice.transaction_id])

        details_table = Table(invoice_details, colWidths=[100, 200])
        details_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))
        content.append(details_table)
        content.append(Spacer(1, 30))

        # From/To addresses
        address_data = [
            ['FROM:', 'BILL TO:'],
            [self._format_address(invoice.from_address),
             self._format_address(invoice.to_address)],
        ]
        address_table = Table(address_data, colWidths=[240, 240])
        address_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#4a5568')),
        ]))
        content.append(address_table)
        content.append(Spacer(1, 30))

        # Line items table
        items_header = ['Description', 'Qty', 'Unit Price', 'Tax', 'Total']
        items_data = [items_header]

        for item in invoice.line_items:
            items_data.append([
                item.description,
                str(item.quantity),
                f"{invoice.currency_symbol}{item.unit_price:,.2f}",
                f"{item.tax_rate}%",
                f"{invoice.currency_symbol}{item.total:,.2f}",
            ])

        items_table = Table(items_data, colWidths=[200, 40, 80, 50, 80])
        items_table.setStyle(TableStyle([
            # Header style
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#6b46c1')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            # Data rows
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),
            ('ALIGN', (0, 1), (0, -1), 'LEFT'),
            # Grid
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('TOPPADDING', (0, 0), (-1, -1), 12),
            # Alternating rows
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f7fafc')]),
        ]))
        content.append(items_table)
        content.append(Spacer(1, 20))

        # Totals
        totals_data = [
            ['Subtotal:', f"{invoice.currency_symbol}{invoice.subtotal:,.2f}"],
            ['Tax:', f"{invoice.currency_symbol}{invoice.total_tax:,.2f}"],
            ['TOTAL:', f"{invoice.currency_symbol}{invoice.total:,.2f}"],
        ]
        totals_table = Table(totals_data, colWidths=[350, 100])
        totals_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 1), 'Helvetica'),
            ('FONTNAME', (0, 2), (-1, 2), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('FONTSIZE', (0, 2), (-1, 2), 14),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('LINEABOVE', (0, 2), (-1, 2), 1, colors.HexColor('#6b46c1')),
            ('TOPPADDING', (0, 2), (-1, 2), 12),
        ]))
        content.append(totals_table)
        content.append(Spacer(1, 30))

        # Payment info
        if invoice.payment_method:
            content.append(Paragraph("Payment Information", styles['SectionTitle']))
            payment_info = f"Payment Method: {invoice.payment_method}"
            if invoice.paid_date:
                payment_info += f" | Paid on: {invoice.paid_date.strftime('%B %d, %Y')}"
            content.append(Paragraph(payment_info, styles['Normal']))
            content.append(Spacer(1, 20))

        # Notes
        if invoice.notes:
            content.append(Paragraph("Notes", styles['SectionTitle']))
            content.append(Paragraph(invoice.notes, styles['Normal']))
            content.append(Spacer(1, 20))

        # Terms
        if invoice.terms:
            content.append(Paragraph("Terms & Conditions", styles['SectionTitle']))
            content.append(Paragraph(invoice.terms, styles['Normal']))
            content.append(Spacer(1, 20))

        # Footer
        content.append(Spacer(1, 30))
        footer_text = (
            f"Thank you for your business!<br/>"
            f"Questions? Contact us at billing@termivoxed.com"
        )
        content.append(Paragraph(footer_text, ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            alignment=TA_CENTER,
            textColor=colors.HexColor('#718096'),
            fontSize=9,
        )))

        # Build PDF
        doc.build(content)

    def _format_address(self, address: InvoiceAddress) -> str:
        """Format address for display"""
        lines = [address.name]
        if address.address_line1:
            lines.append(address.address_line1)
        if address.address_line2:
            lines.append(address.address_line2)

        city_state = []
        if address.city:
            city_state.append(address.city)
        if address.state:
            city_state.append(address.state)
        if address.postal_code:
            city_state.append(address.postal_code)
        if city_state:
            lines.append(', '.join(city_state))

        if address.country:
            lines.append(address.country)
        if address.email:
            lines.append(address.email)
        if address.gstin:
            lines.append(f"GSTIN: {address.gstin}")

        return '\n'.join(lines)

    def _generate_html(self, invoice: Invoice, output_path: Path) -> None:
        """Generate HTML invoice as fallback"""
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Invoice {invoice.invoice_number}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 40px;
            color: #1a202c;
        }}
        .header {{
            border-bottom: 3px solid #6b46c1;
            padding-bottom: 20px;
            margin-bottom: 30px;
        }}
        .invoice-title {{
            font-size: 32px;
            color: #6b46c1;
            margin: 0;
        }}
        .invoice-details {{
            margin-top: 20px;
        }}
        .invoice-details table {{
            border-collapse: collapse;
        }}
        .invoice-details td {{
            padding: 5px 20px 5px 0;
        }}
        .invoice-details td:first-child {{
            font-weight: bold;
            color: #4a5568;
        }}
        .addresses {{
            display: flex;
            justify-content: space-between;
            margin-bottom: 30px;
        }}
        .address {{
            width: 45%;
        }}
        .address h3 {{
            font-size: 12px;
            color: #4a5568;
            margin-bottom: 10px;
            text-transform: uppercase;
        }}
        .items-table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 30px;
        }}
        .items-table th {{
            background: #6b46c1;
            color: white;
            padding: 12px;
            text-align: left;
        }}
        .items-table td {{
            padding: 12px;
            border-bottom: 1px solid #e2e8f0;
        }}
        .items-table tr:nth-child(even) {{
            background: #f7fafc;
        }}
        .totals {{
            text-align: right;
            margin-bottom: 30px;
        }}
        .totals table {{
            margin-left: auto;
        }}
        .totals td {{
            padding: 5px 0 5px 30px;
        }}
        .totals tr:last-child {{
            font-weight: bold;
            font-size: 18px;
            border-top: 2px solid #6b46c1;
        }}
        .totals tr:last-child td {{
            padding-top: 15px;
        }}
        .footer {{
            text-align: center;
            color: #718096;
            font-size: 14px;
            margin-top: 50px;
            padding-top: 20px;
            border-top: 1px solid #e2e8f0;
        }}
        .status-paid {{
            color: #38a169;
            font-weight: bold;
        }}
        .status-pending {{
            color: #d69e2e;
            font-weight: bold;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1 class="invoice-title">INVOICE</h1>
        <div class="invoice-details">
            <table>
                <tr><td>Invoice Number:</td><td>{invoice.invoice_number}</td></tr>
                <tr><td>Date:</td><td>{invoice.invoice_date.strftime('%B %d, %Y')}</td></tr>
                <tr><td>Due Date:</td><td>{invoice.due_date.strftime('%B %d, %Y')}</td></tr>
                <tr><td>Status:</td><td class="status-{'paid' if invoice.status == InvoiceStatus.PAID else 'pending'}">{invoice.status.value.upper()}</td></tr>
                {"<tr><td>Transaction ID:</td><td>" + invoice.transaction_id + "</td></tr>" if invoice.transaction_id else ""}
            </table>
        </div>
    </div>

    <div class="addresses">
        <div class="address">
            <h3>From:</h3>
            <div>{self._format_address(invoice.from_address).replace(chr(10), '<br>')}</div>
        </div>
        <div class="address">
            <h3>Bill To:</h3>
            <div>{self._format_address(invoice.to_address).replace(chr(10), '<br>')}</div>
        </div>
    </div>

    <table class="items-table">
        <thead>
            <tr>
                <th>Description</th>
                <th>Qty</th>
                <th>Unit Price</th>
                <th>Tax</th>
                <th>Total</th>
            </tr>
        </thead>
        <tbody>
            {"".join(f'''
            <tr>
                <td>{item.description}</td>
                <td>{item.quantity}</td>
                <td>{invoice.currency_symbol}{item.unit_price:,.2f}</td>
                <td>{item.tax_rate}%</td>
                <td>{invoice.currency_symbol}{item.total:,.2f}</td>
            </tr>
            ''' for item in invoice.line_items)}
        </tbody>
    </table>

    <div class="totals">
        <table>
            <tr><td>Subtotal:</td><td>{invoice.currency_symbol}{invoice.subtotal:,.2f}</td></tr>
            <tr><td>Tax:</td><td>{invoice.currency_symbol}{invoice.total_tax:,.2f}</td></tr>
            <tr><td>TOTAL:</td><td>{invoice.currency_symbol}{invoice.total:,.2f}</td></tr>
        </table>
    </div>

    {"<div class='notes'><h3>Notes</h3><p>" + invoice.notes + "</p></div>" if invoice.notes else ""}

    <div class="footer">
        <p>Thank you for your business!</p>
        <p>Questions? Contact us at billing@termivoxed.com</p>
    </div>
</body>
</html>
"""
        output_path.write_text(html)

    def generate_from_payment(
        self,
        payment_data: Dict[str, Any],
        customer_data: Dict[str, Any]
    ) -> Path:
        """
        Generate invoice from payment webhook data.

        Args:
            payment_data: Payment data from Stripe/Razorpay webhook
            customer_data: Customer/user data

        Returns:
            Path to generated invoice
        """
        # Determine currency
        currency = payment_data.get('currency', 'USD').upper()
        is_inr = currency == 'INR'

        # Create customer address
        customer_address = InvoiceAddress(
            name=customer_data.get('name', customer_data.get('email', 'Customer')),
            address_line1=customer_data.get('address_line1', ''),
            address_line2=customer_data.get('address_line2'),
            city=customer_data.get('city', ''),
            state=customer_data.get('state', ''),
            postal_code=customer_data.get('postal_code', ''),
            country=customer_data.get('country', 'India' if is_inr else 'USA'),
            email=customer_data.get('email'),
            gstin=customer_data.get('gstin'),
        )

        # Calculate amounts
        amount = payment_data.get('amount', 0)
        if payment_data.get('amount_in_cents', True):
            amount = amount / 100  # Convert from cents/paise

        # Tax calculation (18% GST for India)
        tax_rate = 18 if is_inr else 0
        subtotal = amount / (1 + tax_rate / 100) if tax_rate else amount

        # Create line item
        plan_name = payment_data.get('plan_name', 'TermiVoxed Subscription')
        billing_period = payment_data.get('billing_period', 'monthly')

        line_items = [
            InvoiceLineItem(
                description=f"{plan_name} ({billing_period.capitalize()})",
                quantity=1,
                unit_price=subtotal,
                tax_rate=tax_rate,
                currency=currency,
            )
        ]

        # Create invoice
        invoice_number = self._generate_invoice_number(payment_data)
        now = datetime.now()

        invoice = Invoice(
            invoice_number=invoice_number,
            invoice_date=now,
            due_date=now,  # Paid invoices have same due date
            status=InvoiceStatus.PAID,
            from_address=self.company_address,
            to_address=customer_address,
            line_items=line_items,
            currency=currency,
            currency_symbol='₹' if is_inr else '$',
            payment_method=payment_data.get('payment_method', 'Card'),
            transaction_id=payment_data.get('transaction_id'),
            paid_date=now,
            notes=None,
            terms="This is a computer-generated invoice. No signature required.",
        )

        return self.generate_invoice(invoice)

    def _generate_invoice_number(self, payment_data: Dict[str, Any]) -> str:
        """Generate unique invoice number"""
        date_part = datetime.now().strftime('%Y%m%d')
        payment_id = payment_data.get('transaction_id', '')
        short_id = payment_id[-8:] if payment_id else datetime.now().strftime('%H%M%S')
        return f"INV-{date_part}-{short_id}".upper()


# Singleton instance
_invoice_generator: Optional[InvoicePDFGenerator] = None


def get_invoice_generator(output_dir: Optional[Path] = None) -> InvoicePDFGenerator:
    """Get or create the invoice generator singleton"""
    global _invoice_generator
    if _invoice_generator is None:
        _invoice_generator = InvoicePDFGenerator(output_dir)
    return _invoice_generator
