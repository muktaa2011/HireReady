from django.urls import path
from .views import (
    create_resume,
    dashboard,
    resume_builder,
    resume_preview,
    select_template,
    resume_pdf,
    templates_view,
    ai_resume_analysis,
    ai_analysis_results,
    profile,
)
urlpatterns = [
    path("dashboard/", dashboard, name="dashboard"),
    path("profile/", profile, name="profile"),
    path("templates/", templates_view, name="templates"),
    path("build/<slug:slug>/", resume_builder, name="resume_builder"),
    path("resume/new/", create_resume, name="create_resume"),
    path("resume/<int:resume_id>/templates/", select_template, name="select_template"),
    path(
        "resume/<int:resume_id>/preview/<str:template>/",
        resume_preview,
        name="resume_preview"
    ),
    path(
        "resume/<int:resume_id>/pdf/<str:template>/",
        resume_pdf,
        name="resume_pdf",
    ),
    path("ai/analyze-resume/", ai_resume_analysis, name="ai_resume_analysis"),
    path("ai/analysis-results/", ai_analysis_results, name="ai_analysis_results"),

]
