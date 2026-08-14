import csv
from datetime import date
from io import BytesIO

from django.http import HttpResponse
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from modules.billing.selectors import visible_obligations_for, visible_rent_charges_for
from modules.documents.selectors import visible_documents_for
from modules.leases.selectors import visible_leases_for, visible_tenants_for
from modules.payments.selectors import visible_payments_for

BRAND = colors.HexColor("#D4342B")
INK = colors.HexColor("#121012")
LINE = colors.HexColor("#E5DFDC")


class ExportView(APIView):
    """Exporte les données locatives en CSV ou PDF."""

    permission_classes = (IsAuthenticated,)

    def get(self, request: Request) -> Response:
        export_type = request.query_params.get("type", "payments")
        format_type = request.query_params.get("format", "csv")
        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")

        if format_type == "pdf":
            return self._export_pdf(request.user, export_type, date_from, date_to)

        if export_type == "payments":
            return self._export_payments(request.user, date_from, date_to)
        elif export_type == "charges":
            return self._export_charges(request.user, date_from, date_to)
        elif export_type == "documents":
            return self._export_documents(request.user, date_from, date_to)
        elif export_type == "tenants":
            return self._export_tenants(request.user)
        elif export_type == "leases":
            return self._export_leases(request.user)
        else:
            return Response(
                {"detail": "Type d'export inconnu."},
                status=400,
            )

    def _export_payments(self, user, date_from, date_to):
        queryset = visible_payments_for(user).select_related(
            "allocations__rent_charge__lease__property",
            "allocations__rent_charge__lease__tenant",
        ).order_by("-received_at")

        if date_from:
            queryset = queryset.filter(received_at__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(received_at__date__lte=date_to)

        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = (
            f'attachment; filename="immolib-paiements-{date.today()}.csv"'
        )

        # BOM UTF-8 pour Excel
        response.write("\ufeff")

        writer = csv.writer(response, delimiter=";")
        writer.writerow([
            "Date",
            "Maison",
            "Locataire",
            "Période",
            "Montant",
            "Devise",
            "Moyen",
            "Statut",
            "Référence",
        ])

        for payment in queryset:
            for allocation in payment.allocations.all():
                charge = allocation.rent_charge
                lease = charge.lease if charge else None
                writer.writerow([
                    payment.received_at.strftime("%d/%m/%Y") if payment.received_at else "",
                    lease.property.name if lease and lease.property else "",
                    lease.tenant.full_name if lease and lease.tenant else "",
                    charge.period if charge else "",
                    str(allocation.amount),
                    payment.currency,
                    payment.get_method_display() if hasattr(payment, "get_method_display") else payment.method,
                    payment.get_status_display() if hasattr(payment, "get_status_display") else payment.status,
                    payment.external_reference or "",
                ])

        return response

    def _export_charges(self, user, date_from, date_to):
        queryset = visible_rent_charges_for(user).select_related(
            "lease__property",
            "lease__tenant",
        ).order_by("-period")

        if date_from:
            queryset = queryset.filter(period__gte=date_from[:7])  # YYYY-MM
        if date_to:
            queryset = queryset.filter(period__lte=date_to[:7])

        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = (
            f'attachment; filename="immolib-echéances-{date.today()}.csv"'
        )
        response.write("\ufeff")

        writer = csv.writer(response, delimiter=";")
        writer.writerow([
            "Période",
            "Maison",
            "Locataire",
            "Montant dû",
            "Montant payé",
            "Solde restant",
            "Date d'échéance",
            "Statut",
        ])

        for charge in queryset:
            writer.writerow([
                charge.period,
                charge.lease.property.name if charge.lease and charge.lease.property else "",
                charge.lease.tenant.full_name if charge.lease and charge.lease.tenant else "",
                str(charge.amount_due),
                str(charge.amount_paid),
                str(charge.balance_due),
                charge.due_date.strftime("%d/%m/%Y") if charge.due_date else "",
                charge.get_status_display() if hasattr(charge, "get_status_display") else charge.status,
            ])

        return response

    def _export_documents(self, user, date_from, date_to):
        queryset = visible_documents_for(user).select_related(
            "rent_charge__lease__property",
            "rent_charge__lease__tenant",
        ).order_by("-issued_at")

        if date_from:
            queryset = queryset.filter(issued_at__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(issued_at__date__lte=date_to)

        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = (
            f'attachment; filename="immolib-documents-{date.today()}.csv"'
        )
        response.write("\ufeff")

        writer = csv.writer(response, delimiter=";")
        writer.writerow([
            "Référence",
            "Type",
            "Maison",
            "Locataire",
            "Période",
            "Montant",
            "Devise",
            "Statut",
            "Émis le",
        ])

        for doc in queryset:
            charge = doc.rent_charge
            lease = charge.lease if charge else None
            writer.writerow([
                doc.reference,
                doc.get_document_type_display() if hasattr(doc, "get_document_type_display") else doc.document_type,
                lease.property.name if lease and lease.property else "",
                lease.tenant.full_name if lease and lease.tenant else "",
                doc.period or "",
                str(doc.amount),
                doc.currency,
                doc.get_status_display() if hasattr(doc, "get_status_display") else doc.status,
                doc.issued_at.strftime("%d/%m/%Y") if doc.issued_at else "",
            ])

        return response

    def _export_tenants(self, user):
        queryset = visible_tenants_for(user).select_related("property").order_by("full_name")

        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = (
            f'attachment; filename="immolib-locataires-{date.today()}.csv"'
        )
        response.write("\ufeff")

        writer = csv.writer(response, delimiter=";")
        writer.writerow([
            "Nom complet",
            "Téléphone",
            "Email",
            "Maison",
            "Statut",
        ])

        for tenant in queryset:
            writer.writerow([
                tenant.full_name,
                tenant.phone,
                tenant.email or "",
                tenant.property.name if tenant.property else "",
                tenant.get_status_display() if hasattr(tenant, "get_status_display") else tenant.status,
            ])

        return response

    def _export_leases(self, user):
        queryset = visible_leases_for(user).select_related(
            "property",
            "tenant",
        ).order_by("-start_date")

        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = (
            f'attachment; filename="immolib-baux-{date.today()}.csv"'
        )
        response.write("\ufeff")

        writer = csv.writer(response, delimiter=";")
        writer.writerow([
            "Maison",
            "Locataire",
            "Date de début",
            "Date de fin",
            "Loyer mensuel",
            "Charges",
            "Caution",
            "Jour d'échéance",
            "Statut",
        ])

        for lease in queryset:
            writer.writerow([
                lease.property.name if lease.property else "",
                lease.tenant.full_name if lease.tenant else "",
                lease.start_date.strftime("%d/%m/%Y") if lease.start_date else "",
                lease.end_date.strftime("%d/%m/%Y") if lease.end_date else "En cours",
                str(lease.monthly_rent),
                str(lease.monthly_charges),
                str(lease.security_deposit),
                str(lease.due_day),
                lease.get_status_display() if hasattr(lease, "get_status_display") else lease.status,
            ])

        return response

    def _export_pdf(self, user, export_type, date_from, date_to):
        """Génère un export PDF récapitulatif."""
        output = BytesIO()
        pdf = SimpleDocTemplate(output, pagesize=landscape(A4),
                                leftMargin=15*mm, rightMargin=15*mm,
                                topMargin=15*mm, bottomMargin=15*mm)
        
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle("Title2", parent=styles["Title"],
                                     fontSize=16, textColor=INK, spaceAfter=10)
        header_style = ParagraphStyle("Header", parent=styles["Normal"],
                                      fontSize=8, textColor=colors.white, fontName="Helvetica-Bold")
        cell_style = ParagraphStyle("Cell", parent=styles["Normal"], fontSize=8, leading=10)
        
        story = []
        
        titles = {
            "payments": "Historique des paiements",
            "charges": "Échéances",
            "documents": "Documents",
            "tenants": "Locataires",
            "leases": "Baux",
        }
        
        story.append(Paragraph(f"ImmoLib — {titles.get(export_type, 'Export')}", title_style))
        story.append(Paragraph(f"Généré le {date.today().strftime('%d/%m/%Y')}", styles["Normal"]))
        story.append(Spacer(1, 10*mm))
        
        # En-têtes et données selon le type
        headers, rows = self._get_pdf_data(user, export_type, date_from, date_to)
        
        if not rows:
            story.append(Paragraph("Aucune donnée à exporter.", styles["Normal"]))
        else:
            col_count = len(headers)
            col_width = (landscape(A4)[0] - 30*mm) / col_count
            col_widths = [col_width] * col_count
            
            header_row = [Paragraph(h, header_style) for h in headers]
            table_data = [header_row]
            for row in rows:
                table_data.append([Paragraph(str(cell), cell_style) for cell in row])
            
            table = Table(table_data, colWidths=col_widths)
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), BRAND),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("GRID", (0, 0), (-1, -1), 0.5, LINE),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F9F6F5")]),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ]))
            story.append(table)
        
        pdf.build(story)
        content = output.getvalue()
        
        response = HttpResponse(content, content_type="application/pdf")
        response["Content-Disposition"] = (
            f'attachment; filename="immolib-{export_type}-{date.today()}.pdf"'
        )
        return response
    
    def _get_pdf_data(self, user, export_type, date_from, date_to):
        """Retourne (headers, rows) pour le PDF."""
        if export_type == "payments":
            return self._get_payments_data(user, date_from, date_to)
        elif export_type == "charges":
            return self._get_charges_data(user, date_from, date_to)
        elif export_type == "documents":
            return self._get_documents_data(user, date_from, date_to)
        elif export_type == "tenants":
            return self._get_tenants_data(user)
        elif export_type == "leases":
            return self._get_leases_data(user)
        return [], []
    
    def _get_payments_data(self, user, date_from, date_to):
        queryset = visible_payments_for(user).select_related(
            "allocations__rent_charge__lease__property",
            "allocations__rent_charge__lease__tenant",
        ).order_by("-received_at")
        if date_from:
            queryset = queryset.filter(received_at__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(received_at__date__lte=date_to)
        
        headers = ["Date", "Maison", "Locataire", "Période", "Montant", "Devise", "Moyen", "Statut"]
        rows = []
        for payment in queryset:
            for allocation in payment.allocations.all():
                charge = allocation.rent_charge
                lease = charge.lease if charge else None
                rows.append([
                    payment.received_at.strftime("%d/%m/%Y") if payment.received_at else "",
                    lease.property.name if lease and lease.property else "",
                    lease.tenant.full_name if lease and lease.tenant else "",
                    charge.period if charge else "",
                    str(allocation.amount),
                    payment.currency,
                    payment.get_method_display() if hasattr(payment, "get_method_display") else payment.method,
                    payment.get_status_display() if hasattr(payment, "get_status_display") else payment.status,
                ])
        return headers, rows
    
    def _get_charges_data(self, user, date_from, date_to):
        queryset = visible_rent_charges_for(user).select_related(
            "lease__property", "lease__tenant",
        ).order_by("-period")
        if date_from:
            queryset = queryset.filter(period__gte=date_from[:7])
        if date_to:
            queryset = queryset.filter(period__lte=date_to[:7])
        
        headers = ["Période", "Maison", "Locataire", "Dû", "Payé", "Solde", "Échéance", "Statut"]
        rows = []
        for charge in queryset:
            rows.append([
                charge.period,
                charge.lease.property.name if charge.lease and charge.lease.property else "",
                charge.lease.tenant.full_name if charge.lease and charge.lease.tenant else "",
                str(charge.amount_due),
                str(charge.amount_paid),
                str(charge.balance_due),
                charge.due_date.strftime("%d/%m/%Y") if charge.due_date else "",
                charge.get_status_display() if hasattr(charge, "get_status_display") else charge.status,
            ])
        return headers, rows
    
    def _get_documents_data(self, user, date_from, date_to):
        queryset = visible_documents_for(user).select_related(
            "rent_charge__lease__property", "rent_charge__lease__tenant",
        ).order_by("-issued_at")
        if date_from:
            queryset = queryset.filter(issued_at__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(issued_at__date__lte=date_to)
        
        headers = ["Référence", "Type", "Maison", "Locataire", "Période", "Montant", "Statut"]
        rows = []
        for doc in queryset:
            charge = doc.rent_charge
            lease = charge.lease if charge else None
            rows.append([
                doc.reference,
                doc.get_document_type_display() if hasattr(doc, "get_document_type_display") else doc.document_type,
                lease.property.name if lease and lease.property else "",
                lease.tenant.full_name if lease and lease.tenant else "",
                doc.period or "",
                str(doc.amount),
                doc.get_status_display() if hasattr(doc, "get_status_display") else doc.status,
            ])
        return headers, rows
    
    def _get_tenants_data(self, user):
        queryset = visible_tenants_for(user).select_related("property").order_by("full_name")
        headers = ["Nom", "Téléphone", "Email", "Maison", "Statut"]
        rows = []
        for tenant in queryset:
            rows.append([
                tenant.full_name,
                tenant.phone,
                tenant.email or "",
                tenant.property.name if tenant.property else "",
                tenant.get_status_display() if hasattr(tenant, "get_status_display") else tenant.status,
            ])
        return headers, rows
    
    def _get_leases_data(self, user):
        queryset = visible_leases_for(user).select_related("property", "tenant").order_by("-start_date")
        headers = ["Maison", "Locataire", "Début", "Fin", "Loyer", "Charges", "Caution", "Jour", "Statut"]
        rows = []
        for lease in queryset:
            rows.append([
                lease.property.name if lease.property else "",
                lease.tenant.full_name if lease.tenant else "",
                lease.start_date.strftime("%d/%m/%Y") if lease.start_date else "",
                lease.end_date.strftime("%d/%m/%Y") if lease.end_date else "En cours",
                str(lease.monthly_rent),
                str(lease.monthly_charges),
                str(lease.security_deposit),
                str(lease.due_day),
                lease.get_status_display() if hasattr(lease, "get_status_display") else lease.status,
            ])
        return headers, rows
