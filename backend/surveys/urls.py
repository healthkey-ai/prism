from django.urls import path

from . import views

urlpatterns = [
    path("surveys/", views.surveys),
    path("surveys/<uuid:survey_id>/questions/", views.questions),
    path("surveys/<uuid:survey_id>/crosstab/", views.survey_crosstab),
]
