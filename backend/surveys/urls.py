from django.urls import path

from . import views

urlpatterns = [
    path("surveys/", views.surveys),
    path("surveys/<uuid:survey_id>/questions/", views.questions),
    path("surveys/<uuid:survey_id>/responses/", views.survey_responses),
    path("surveys/<uuid:survey_id>/responses/export/", views.survey_responses_export),
    path("surveys/<uuid:survey_id>/crosstab/", views.survey_crosstab),
]
