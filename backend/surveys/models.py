"""Read-only mirrors of PROMOP's PROlog survey tables."""
from django.db import models


class Survey(models.Model):
    id = models.UUIDField(primary_key=True)
    slug = models.SlugField(max_length=120)
    title = models.CharField(max_length=255)

    class Meta:
        managed = False
        db_table = "prolog_surveys_survey"


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


class SurveyLinkedContact(models.Model):
    """Optional email contact a respondent provided when submitting their survey."""
    response = models.OneToOneField(
        SurveyResponse, on_delete=models.DO_NOTHING, related_name="linked_contact",
        db_column="response_id",
    )
    email = models.CharField(max_length=254)
    # Mirrored from PROMOP once healthkey-ai/promop#2084 adds the column.
    # Until then, filtering on this field raises ProgrammingError which is
    # caught by _cohort_response_ids() in views.py to degrade gracefully.
    patient_id = models.UUIDField(null=True, db_column="patient_id")

    class Meta:
        managed = False
        db_table = "prolog_surveys_surveylinkedcontact"
