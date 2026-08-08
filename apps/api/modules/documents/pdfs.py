from io import BytesIO
from pathlib import Path
from decimal import Decimal
from xml.sax.saxutils import escape

import reportlab
from django.utils import timezone
from django.utils.translation import gettext as _
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from modules.i18n.format import format_long_date, format_month_name, format_money

from .models import RentalDocument


BRAND = colors.HexColor("#D4342B")
BRAND_DARK = colors.HexColor("#A92721")
BRAND_SOFT = colors.HexColor("#FBE9E7")
INK = colors.HexColor("#121012")
MUTED = colors.HexColor("#696562")
LINE = colors.HexColor("#E5DFDC")
CANVAS = colors.HexColor("#F9F6F5")
ERROR = colors.HexColor("#B42318")
ERROR_SOFT = colors.HexColor("#FEF3F2")

REGULAR_FONT = "ImmoLibVera"
BOLD_FONT = "ImmoLibVeraBold"


def _register_fonts() -> None:
    if REGULAR_FONT in pdfmetrics.getRegisteredFontNames():
        return
    font_directory = Path(reportlab.__file__).resolve().parent / "fonts"
    pdfmetrics.registerFont(
        TTFont(REGULAR_FONT, str(font_directory / "Vera.ttf"))
    )
    pdfmetrics.registerFont(
        TTFont(BOLD_FONT, str(font_directory / "VeraBd.ttf"))
    )


def _date_label(value) -> str:
    return format_long_date(value)


def _money_label(amount, currency: str) -> str:
    return format_money(amount, currency)


def _safe(value) -> str:
    return escape(str(value or ""))


def rental_document_pdf_filename(document: RentalDocument) -> str:
    prefix = {
        RentalDocument.Type.RENT_RECEIPT: _("quittance"),
    }.get(document.document_type, _("recu"))
    return f"{prefix}-{document.reference}.pdf"


def build_rental_document_pdf(document: RentalDocument) -> bytes:
    """Construit un PDF A4 depuis l'instantané immuable du document.

    Le PDF est genere dans la langue de l'utilisateur : la locale active
    (middleware ou override explicite) fournit les libelles, mois, dates
    et montants localises.
    """

    _register_fonts()
    output = BytesIO()
    title = {
        RentalDocument.Type.RENT_RECEIPT: _("Quittance de loyer"),
    }.get(document.document_type, _("Reçu de paiement"))
    active = document.status == RentalDocument.Status.ACTIVE
    status_label = _("ACTIF") if active else _("INVALIDE")
    status_color = BRAND_DARK if active else ERROR
    status_background = BRAND_SOFT if active else ERROR_SOFT

    pdf = SimpleDocTemplate(
        output,
        pagesize=A4,
        leftMargin=22 * mm,
        rightMargin=22 * mm,
        topMargin=19 * mm,
        bottomMargin=20 * mm,
        title=f"{str(title)} - {document.reference}",
        author="ImmoLib",
        subject=str(_("Justificatif de gestion locative")),
    )

    styles = getSampleStyleSheet()
    body = ParagraphStyle(
        "ImmoLibBody",
        parent=styles["BodyText"],
        fontName=REGULAR_FONT,
        fontSize=9.5,
        leading=15,
        textColor=INK,
    )
    small = ParagraphStyle(
        "ImmoLibSmall",
        parent=body,
        fontSize=7.5,
        leading=11,
        textColor=MUTED,
    )
    label = ParagraphStyle(
        "ImmoLibLabel",
        parent=small,
        fontName=BOLD_FONT,
        fontSize=7,
        leading=10,
        textColor=MUTED,
        spaceAfter=2,
    )
    value = ParagraphStyle(
        "ImmoLibValue",
        parent=body,
        fontName=BOLD_FONT,
        fontSize=9.5,
        leading=13,
    )
    centered = ParagraphStyle(
        "ImmoLibCentered",
        parent=body,
        alignment=TA_CENTER,
    )
    right = ParagraphStyle(
        "ImmoLibRight",
        parent=body,
        alignment=TA_RIGHT,
    )

    def field(field_label: str, field_value: str, detail: str = ""):
        content = [
            Paragraph(_safe(field_label).upper(), label),
            Paragraph(_safe(field_value), value),
        ]
        if detail:
            content.append(Paragraph(_safe(detail), small))
        return content

    brand_mark = Table(
        [[Paragraph("<b>IL</b>", ParagraphStyle("Mark", parent=centered, fontName=BOLD_FONT, fontSize=13, textColor=colors.white))]],
        colWidths=[11 * mm],
        rowHeights=[11 * mm],
    )
    brand_mark.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), BRAND),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BOX", (0, 0), (-1, -1), 0.5, BRAND),
            ]
        )
    )
    brand_text = [
        Paragraph("<b>ImmoLib</b>", ParagraphStyle("Brand", parent=body, fontName=BOLD_FONT, fontSize=14, leading=16)),
        Paragraph(_("GESTION LOCATIVE"), label),
    ]
    status = Table(
        [[Paragraph(status_label, ParagraphStyle("Status", parent=centered, fontName=BOLD_FONT, fontSize=7.5, textColor=status_color))]],
        colWidths=[25 * mm],
        rowHeights=[8 * mm],
    )
    status.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), status_background),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BOX", (0, 0), (-1, -1), 0.5, status_color),
            ]
        )
    )
    header = Table(
        [[brand_mark, brand_text, status]],
        colWidths=[14 * mm, 112 * mm, 34 * mm],
        rowHeights=[14 * mm],
    )
    header.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("LINEBELOW", (0, 0), (-1, -1), 1.5, INK),
            ]
        )
    )

    period = f"{document.period_start.year}-{document.period_start.month:02d}"
    title_block = [
        Spacer(1, 15 * mm),
        Paragraph(
            _safe(document.reference),
            ParagraphStyle(
                "Reference",
                parent=centered,
                fontName=BOLD_FONT,
                fontSize=7.5,
                leading=11,
                textColor=BRAND,
            ),
        ),
        Spacer(1, 2.5 * mm),
        Paragraph(
            title.upper(),
            ParagraphStyle(
                "Title",
                parent=centered,
                fontName=BOLD_FONT,
                fontSize=21,
                leading=27,
                textColor=INK,
            ),
        ),
        Spacer(1, 2 * mm),
        Paragraph(
            _("Période de {month}").format(month=format_month_name(period)),
            centered,
        ),
        Spacer(1, 11 * mm),
    ]

    details = Table(
        [
            [
                field(_("Bailleur"), document.owner_name),
                field(_("Locataire"), document.tenant_name),
            ],
            [
                field(_("Maison"), document.house_name, document.house_address),
                field(
                    _("Période"),
                    _("Du {date}").format(date=_date_label(document.period_start)),
                    _("au {date}").format(date=_date_label(document.period_end)),
                ),
            ],
            [
                field(
                    _("Moyen de paiement"),
                    document.payment_method or _("Non précisé"),
                ),
                field(
                    _("Émis le"),
                    _date_label(timezone.localtime(document.issued_at).date()),
                ),
            ],
        ],
        colWidths=[80 * mm, 80 * mm],
    )
    details.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOX", (0, 0), (-1, -1), 0.6, LINE),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, LINE),
                ("LEFTPADDING", (0, 0), (-1, -1), 5 * mm),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5 * mm),
                ("TOPPADDING", (0, 0), (-1, -1), 4 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4 * mm),
            ]
        )
    )

    amount_table = Table(
        [[
            Paragraph(_("MONTANT DOCUMENTÉ"), ParagraphStyle("AmountLabel", parent=label, textColor=BRAND_DARK)),
            Paragraph(
                _safe(_money_label(document.amount, document.currency)),
                ParagraphStyle("Amount", parent=right, fontName=BOLD_FONT, fontSize=17, leading=21, textColor=INK),
            ),
        ]],
        colWidths=[76 * mm, 84 * mm],
    )
    amount_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), BRAND_SOFT),
                ("BOX", (0, 0), (-1, -1), 0.6, BRAND),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5 * mm),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5 * mm),
                ("TOPPADDING", (0, 0), (-1, -1), 5 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5 * mm),
            ]
        )
    )

    breakdown_table = None
    if document.document_type == RentalDocument.Type.RENT_RECEIPT and document.breakdown:
        breakdown_rows = [
            [
                Paragraph(_("AFFECTATION"), label),
                Paragraph(_("MONTANT"), ParagraphStyle("BreakdownAmountLabel", parent=label, alignment=TA_RIGHT)),
            ]
        ]
        breakdown_rows.extend(
            [
                [
                    Paragraph(_safe(item.get("label", _("Obligation"))), body),
                    Paragraph(
                        _safe(
                            _money_label(
                                Decimal(str(item.get("amount", 0))),
                                document.currency,
                            )
                        ),
                        ParagraphStyle("BreakdownAmount", parent=body, alignment=TA_RIGHT),
                    ),
                ]
                for item in document.breakdown
            ]
        )
        breakdown_table = Table(breakdown_rows, colWidths=[104 * mm, 56 * mm])
        breakdown_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), CANVAS),
                    ("BOX", (0, 0), (-1, -1), 0.6, LINE),
                    ("INNERGRID", (0, 0), (-1, -1), 0.35, LINE),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4 * mm),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4 * mm),
                    ("TOPPADDING", (0, 0), (-1, -1), 2.5 * mm),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5 * mm),
                ]
            )
        )

    if document.document_type == RentalDocument.Type.RENT_RECEIPT:
        statement = _(
            "Cette quittance atteste que l'échéance de loyer indiquée ci-dessus "
            "a été entièrement soldée. Elle est distincte de chaque reçu émis "
            "pour un versement partiel."
        )
    else:
        statement = _(
            "Ce reçu atteste de l'enregistrement du versement indiqué ci-dessus. "
            "Il ne constitue une quittance de loyer que si l'échéance concernée "
            "est entièrement soldée."
        )

    verification_data = [
        [Paragraph(_("VÉRIFICATION"), label), Paragraph("", small)],
        [Paragraph(_("Référence"), small), Paragraph(_safe(document.reference), value)],
        [Paragraph(_("Statut à l'émission du PDF"), small), Paragraph(status_label, ParagraphStyle("VerificationStatus", parent=value, textColor=status_color))],
    ]
    if not active and document.void_reason:
        verification_data.append(
            [Paragraph(_("Motif"), small), Paragraph(_safe(document.void_reason), body)]
        )
    verification = Table(verification_data, colWidths=[56 * mm, 104 * mm])
    verification.setStyle(
        TableStyle(
            [
                ("SPAN", (0, 0), (-1, 0)),
                ("BACKGROUND", (0, 0), (-1, -1), CANVAS),
                ("BOX", (0, 0), (-1, -1), 0.6, LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5 * mm),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5 * mm),
                ("TOPPADDING", (0, 0), (-1, -1), 3 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3 * mm),
            ]
        )
    )

    story = [
        header,
        *title_block,
        details,
        Spacer(1, 7 * mm),
        amount_table,
    ]
    if breakdown_table is not None:
        story.extend([Spacer(1, 5 * mm), breakdown_table])
    story.extend([
        Spacer(1, 7 * mm),
        Paragraph(statement, body),
        Spacer(1, 7 * mm),
        KeepTogether(verification),
    ])

    def decorate_page(canvas, doc):
        canvas.saveState()
        if not active:
            canvas.setFillColor(colors.Color(0.7, 0.1, 0.1, alpha=0.08))
            canvas.setFont(BOLD_FONT, 39)
            canvas.translate(A4[0] / 2, A4[1] / 2)
            canvas.rotate(35)
            canvas.drawCentredString(0, 0, str(_("DOCUMENT INVALIDE")))
            canvas.rotate(-35)
            canvas.translate(-A4[0] / 2, -A4[1] / 2)
        canvas.setStrokeColor(LINE)
        canvas.line(22 * mm, 14 * mm, A4[0] - 22 * mm, 14 * mm)
        canvas.setFont(REGULAR_FONT, 7)
        canvas.setFillColor(MUTED)
        canvas.drawString(22 * mm, 9.5 * mm, str(_("Document généré par ImmoLib")))
        canvas.drawRightString(
            A4[0] - 22 * mm,
            9.5 * mm,
            str(_("Page {number}").format(number=doc.page)),
        )
        canvas.restoreState()

    pdf.build(story, onFirstPage=decorate_page, onLaterPages=decorate_page)
    return output.getvalue()
