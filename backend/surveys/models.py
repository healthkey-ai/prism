"""Read-only mirrors of PROMOP's PROlog survey tables, and which org owns each survey."""
from django.db import models

from accounts.promop_models import PromopOrganization


class Survey(models.Model):
    id = models.UUIDField(primary_key=True)
    slug = models.SlugField(max_length=120)
    title = models.CharField(max_length=255)

    class Meta:
        managed = False
        db_table = "prolog_surveys_survey"

    def __str__(self):
        return self.title


class SurveyVersion(models.Model):
    survey = models.ForeignKey(Survey, on_delete=models.DO_NOTHING, related_name="versions")
    version = models.CharField(max_length=32)
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "prolog_surveys_surveyversion"


class SurveyQuestion(models.Model):
    survey_version = models.ForeignKey(SurveyVersion, on_delete=models.DO_NOTHING, related_name="questions")
    key = models.CharField(max_length=128)
    type = models.CharField(max_length=16)
    order = models.PositiveIntegerField()
    text = models.TextField()

    class Meta:
        managed = False
        db_table = "prolog_surveys_surveyquestion"


class SurveyOption(models.Model):
    question = models.ForeignKey(SurveyQuestion, on_delete=models.DO_NOTHING, related_name="options")
    key = models.CharField(max_length=128)
    order = models.PositiveIntegerField()
    label = models.TextField()
    free_text = models.BooleanField()

    class Meta:
        managed = False
        db_table = "prolog_surveys_surveyoption"


class SurveyResponse(models.Model):
    id = models.UUIDField(primary_key=True)
    survey_version = models.ForeignKey(SurveyVersion, on_delete=models.DO_NOTHING, related_name="responses")
    status = models.CharField(max_length=16)

    class Meta:
        managed = False
        db_table = "prolog_surveys_surveyresponse"


class SurveyAnswer(models.Model):
    response = models.ForeignKey(SurveyResponse, on_delete=models.DO_NOTHING, related_name="answers")
    question_key = models.CharField(max_length=128)
    value = models.JSONField()

    class Meta:
        managed = False
        db_table = "prolog_surveys_surveyanswer"


class SurveyOrganization(models.Model):
    """The organisation that owns a survey's results. PRism owns this table.

    PROlog surveys carry no organisation, so staff record here whose survey it
    is. The owning org's org_admin and analyst users see the survey's
    aggregates; a survey with no owner is visible to staff only.
    """
    # No database constraints: both tables belong to PROMOP, and PRism's
    # migrate can run before PROMOP has created them.
    survey = models.OneToOneField(
        Survey, on_delete=models.DO_NOTHING, db_constraint=False, related_name="ownership",
    )
    organization = models.ForeignKey(
        PromopOrganization, on_delete=models.DO_NOTHING, db_constraint=False, related_name="+",
    )

    class Meta:
        db_table = "prism_survey_organization"

    def __str__(self):
        return f"{self.survey} → {self.organization}"
