from django.contrib import admin

from .models import SurveyOrganization


@admin.register(SurveyOrganization)
class SurveyOrganizationAdmin(admin.ModelAdmin):
    """Which org owns each survey's results: its org_admin and analyst users see them."""
    list_display = ["survey", "organization"]
    search_fields = ["survey__title", "survey__slug", "organization__name"]
    ordering = ["survey__title"]
