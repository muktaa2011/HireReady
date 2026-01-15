from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Max
from django.http import HttpResponse, JsonResponse
from django.template.loader import render_to_string
from django.conf import settings
from io import BytesIO
from datetime import datetime
import re
import json

from pypdf import PdfReader
from xhtml2pdf import pisa

try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

from .models import Resume, ResumeTemplate
from .forms import ResumeForm


def _calculate_ats_score_from_text(text: str) -> int:
    """
    Very simple ATS score heuristic based on sections, keywords and length.
    Returns an integer between 0 and 100.
    """
    if not text:
        return 0

    text_lower = text.lower()
    score = 0.0

    # 1) Check for common resume sections (40% of score)
    sections = [
        "summary",
        "objective",
        "career objective",
        "education",
        "experience",
        "work history",
        "projects",
        "skills",
        "certifications",
    ]
    section_weight = 40.0
    per_section = section_weight / len(sections)
    for s in sections:
        if s in text_lower:
            score += per_section

    # 2) Check for common keywords (40% of score)
    keywords = [
        "python",
        "django",
        "sql",
        "rest api",
        "html",
        "css",
        "javascript",
        "react",
        "machine learning",
        "data analysis",
        "git",
        "docker",
    ]
    keyword_weight = 40.0
    per_kw = keyword_weight / len(keywords)
    found_keywords = 0
    for kw in keywords:
        if kw in text_lower:
            found_keywords += 1
    score += min(found_keywords * per_kw, keyword_weight)

    # 3) Length / readability (20% of score)
    words = re.findall(r"\w+", text_lower)
    word_count = len(words)
    if 300 <= word_count <= 1200:
        score += 20.0
    elif 150 <= word_count < 300 or 1200 < word_count <= 2000:
        score += 10.0

    # Clamp between 0 and 100
    return int(max(0, min(100, round(score))))


def _split_lines(text: str):
    if not text:
        return []
    return [line.strip() for line in text.splitlines() if line.strip()]


def _split_name(full_name: str):
    """Split full name into first and last name parts."""
    if not full_name:
        return ["", ""]
    parts = full_name.strip().split()
    if len(parts) == 0:
        return ["", ""]
    elif len(parts) == 1:
        return [parts[0], ""]
    else:
        return [parts[0], " ".join(parts[1:])]


def _parse_education(resume: Resume):
    quals = _split_lines(resume.edu_qualification)
    years = resume.edu_year.splitlines() if resume.edu_year else []
    colleges = resume.edu_college.splitlines() if resume.edu_college else []
    universities = resume.edu_university.splitlines() if resume.edu_university else []
    cgpas = resume.edu_cgpa.splitlines() if resume.edu_cgpa else []
    classes = resume.edu_class.splitlines() if resume.edu_class else []

    rows = []
    for idx, qual in enumerate(quals):
        rows.append({
            "qualification": qual,
            "year": years[idx] if idx < len(years) else "",
            "college": colleges[idx] if idx < len(colleges) else "",
            "university": universities[idx] if idx < len(universities) else "",
            "cgpa": cgpas[idx] if idx < len(cgpas) else "",
            "class": classes[idx] if idx < len(classes) else "",
        })
    return rows


def home(request):
    return render(request, "index.html")


@login_required(login_url="/register/")
def dashboard(request):
    print("DEBUG: dashboard accessed by", request.user)

    resumes = Resume.objects.filter(user=request.user)

    total_resumes = resumes.count()
    analyzed_count = resumes.filter(analyzed=True).count()

    avg_ats = resumes.aggregate(avg=Avg("ats_score"))["avg"] or 0
    last_updated = resumes.aggregate(last=Max("updated_at"))["last"]

    ats_score_result = None
    ats_error = None

    # Handle ATS score calculation from uploaded PDF
    if request.method == "POST":
        uploaded = request.FILES.get("resume_pdf")
        if not uploaded:
            ats_error = "Please upload a PDF file."
        elif not uploaded.name.lower().endswith(".pdf"):
            ats_error = "Only PDF files are supported."
        else:
            try:
                reader = PdfReader(uploaded)
                text_parts = []
                for page in reader.pages:
                    page_text = page.extract_text() or ""
                    text_parts.append(page_text)
                full_text = "\n".join(text_parts).strip()
                if not full_text:
                    ats_error = "Could not read any text from the PDF. Make sure it is not just an image."
                else:
                    ats_score_result = _calculate_ats_score_from_text(full_text)
            except Exception as e:
                ats_error = "Error reading PDF file. Please try another file."

    context = {
        "total_resumes": total_resumes,
        "avg_ats": round(avg_ats),
        "analyzed_count": analyzed_count,
        "last_updated": last_updated,
        "resumes": resumes,
        "ats_score_result": ats_score_result,
        "ats_error": ats_error,
    }

    return render(request, "dashboard.html", context)


def templates_view(request):
    templates = ResumeTemplate.objects.all()
    return render(request, "templates.html", {"templates": templates})


@login_required
def resume_builder(request, slug):
    request.session["selected_template"] = slug
    return redirect("dashboard")  # later replace with builder page


@login_required
def create_resume(request):
    if request.method == "POST":
        form = ResumeForm(request.POST, request.FILES)
        if form.is_valid():
            resume = form.save(commit=False)
            resume.user = request.user
            # Set default values for ATS score and analyzed
            resume.ats_score = 0
            resume.analyzed = False
            # Backwards compatibility if legacy columns exist
            if hasattr(resume, "title") and not resume.title:
                resume.title = resume.full_name
            if hasattr(resume, "content") and not resume.content:
                resume.content = resume.career_objective
            resume.save()

            # Redirect to template selection page
            return redirect("select_template", resume_id=resume.id)
        else:
            # Form has errors, will be displayed in template
            print("Form errors:", form.errors)
    else:
        form = ResumeForm()

    return render(request, "create_resume.html", {"form": form})


@login_required
def select_template(request, resume_id):
    resume = get_object_or_404(Resume, id=resume_id, user=request.user)
    return render(request, "select_template.html", {
        "resume": resume
    })


@login_required
def resume_preview(request, resume_id, template):
    resume = get_object_or_404(Resume, id=resume_id, user=request.user)

    allowed_templates = [
        "professional_classic",
        "creative_minimal",
        "modern_photo_style",
    ]

    if template not in allowed_templates:
        return redirect("select_template", resume_id=resume.id)

    education_rows = _parse_education(resume)
    name_parts = _split_name(resume.full_name)

    return render(
        request,
        f"resume/{template}.html",
        {
            "r": resume,
            "template_slug": template,
            "education_rows": education_rows,
            "skills_list": _split_lines(resume.skills),
            "projects_list": _split_lines(resume.projects),
            "achievements_list": _split_lines(resume.achievements),
            "certifications_list": _split_lines(resume.certifications),
            "languages_list": _split_lines(resume.languages),
            "hobbies_list": _split_lines(resume.hobbies),
            "first_name": name_parts[0],
            "last_name": name_parts[1],
        },
    )


@login_required
def resume_pdf(request, resume_id, template):
    """
    Generate a PDF for the chosen resume template.
    Uses the same HTML template as the preview.
    """
    resume = get_object_or_404(Resume, id=resume_id, user=request.user)

    allowed_templates = [
        "professional_classic",
        "creative_minimal",
        "modern_photo_style",
    ]

    if template not in allowed_templates:
        return redirect("select_template", resume_id=resume.id)

    education_rows = _parse_education(resume)
    name_parts = _split_name(resume.full_name)

    # Render HTML from the chosen template
    html_string = render_to_string(
        f"resume/{template}.html",
        {
            "r": resume,
            "template_slug": template,
            "education_rows": education_rows,
            "skills_list": _split_lines(resume.skills),
            "projects_list": _split_lines(resume.projects),
            "achievements_list": _split_lines(resume.achievements),
            "certifications_list": _split_lines(resume.certifications),
            "languages_list": _split_lines(resume.languages),
            "hobbies_list": _split_lines(resume.hobbies),
            "first_name": name_parts[0],
            "last_name": name_parts[1],
        },
    )

    # Compact CSS to stay within 1–2 pages
    html = f"""
    <style>
        @page {{ size: A4; margin: 14mm; }}
        body {{ font-family: Arial, sans-serif; font-size: 11pt; line-height: 1.35; }}
        h1 {{ font-size: 20pt; margin: 0 0 6px 0; }}
        h2 {{ font-size: 13pt; margin: 12px 0 6px 0; }}
        p, li {{ font-size: 11pt; margin: 0 0 4px 0; }}
        .section, div {{ page-break-inside: avoid; }}
    </style>
    {html_string}
    """

    result = BytesIO()
    pdf = pisa.CreatePDF(html, dest=result, link_callback=None)

    if pdf.err:
        return HttpResponse("Error generating PDF", status=500)

    response = HttpResponse(result.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="resume_{resume_id}.pdf"'
    return response


@login_required
def ai_resume_analysis(request):
    """
    AI-powered resume analysis using Google Generative AI.
    Accepts PDF from user, reads it, converts to string, and analyzes using Gemini API.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Only POST requests allowed"}, status=405)

    if not GENAI_AVAILABLE:
        return JsonResponse({"error": "Google Generative AI library not installed. Run: pip install google-generativeai"}, status=500)

    api_key = getattr(settings, "GOOGLE_AI_API_KEY", None)
    if not api_key or api_key == "YOUR_GOOGLE_AI_API_KEY_HERE":
        return JsonResponse({"error": "Google AI API key not configured. Please set GOOGLE_AI_API_KEY in settings.py"}, status=500)

    # Step 1: Accept PDF from user
    uploaded = request.FILES.get("resume_pdf")
    if not uploaded:
        return JsonResponse({"error": "Please upload a PDF file."}, status=400)

    if not uploaded.name.lower().endswith(".pdf"):
        return JsonResponse({"error": "Only PDF files are supported."}, status=400)

    try:
        # Step 2: Read PDF using pypdf and convert to string
        # Reset file pointer to beginning in case it was read before
        uploaded.seek(0)
        
        # Read PDF file
        reader = PdfReader(uploaded)
        
        # Extract text from all pages
        text_parts = []
        for page_num, page in enumerate(reader.pages, start=1):
            try:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
            except Exception as page_err:
                # Continue with other pages if one fails
                continue
        
        # Step 3: Convert PDF content to string
        resume_text = "\n".join(text_parts).strip()
        
        if not resume_text:
            return JsonResponse({
                "error": "Could not read any text from the PDF. Make sure it is not just an image or scanned document."
            }, status=400)

        # Step 4: Configure Gemini API
        genai.configure(api_key=api_key)
        
        # Test API connection by trying to list available models (optional, for debugging)
        available_model_hint = None
        try:
            # Try to get a list of available models (this helps with debugging)
            models_list = list(genai.list_models())
            if models_list:
                # Extract model names that support generateContent
                working_models = []
                for m in models_list:
                    if hasattr(m, 'supported_generation_methods') and 'generateContent' in m.supported_generation_methods:
                        model_name = m.name.replace('models/', '') if hasattr(m, 'name') else str(m)
                        working_models.append(model_name)
                if working_models:
                    available_model_hint = working_models[0]  # Use first available model
        except Exception:
            # If listing fails, continue with default models
            pass
        
        # Step 5: Create prompt with the resume text string
        prompt = f"""Analyze the following resume and provide detailed career recommendations in JSON format.

Resume Content:
{resume_text}

Please provide a JSON response with the following structure:
{{
    "top_companies": [
        {{
            "name": "Company Name",
            "location": "City, State/Country",
            "match_reason": "Why this company matches the candidate",
            "hiring_process": "Step-by-step hiring process (interview rounds, tests, etc.)",
            "study_resources": ["Resource 1", "Resource 2", "Resource 3"]
        }}
    ],
    "study_plan": {{
        "overview": "Overall study plan description for the candidate",
        "timeline": "Suggested timeline (e.g., 3 months, 6 months)",
        "weekly_schedule": [
            {{
                "day": "Monday",
                "topics": ["Topic 1", "Topic 2"],
                "hours": 2,
                "activities": "Description of activities"
            }}
        ],
        "skill_gaps": ["Skill 1 to improve", "Skill 2 to learn"],
        "recommended_courses": [
            {{
                "name": "Course Name",
                "platform": "Platform (Coursera, Udemy, etc.)",
                "duration": "Duration",
                "description": "Why this course is recommended"
            }}
        ],
        "practice_projects": [
            {{
                "title": "Project Title",
                "description": "Project description",
                "technologies": ["Tech 1", "Tech 2"],
                "difficulty": "Beginner/Intermediate/Advanced"
            }}
        ],
        "certifications": [
            {{
                "name": "Certification Name",
                "issuer": "Issuing Organization",
                "importance": "Why this certification matters"
            }}
        ]
    }}
}}

Provide exactly 10 companies that would be a good fit based on the candidate's skills, experience, and qualifications. Include:
- Real companies that actually hire for these roles
- Specific locations (cities)
- Detailed hiring processes (e.g., "1. Online Application 2. Phone Screen 3. Technical Assessment 4. On-site Interview 5. HR Round")
- Practical study resources (courses, books, websites, certifications)

Create a comprehensive study plan that includes:
- Weekly schedule with specific topics and activities
- Skill gaps to address
- Recommended courses with platforms and durations
- Practice projects to build portfolio
- Important certifications to pursue

Return ONLY valid JSON, no additional text."""

        # Step 6: Use Gemini API to analyze - try available models
        # Updated model names (as of 2024) - try most common working models
        # Try models in order of preference: fastest/cheapest first
        model_names = [
            'gemini-1.5-flash',      # Fast and efficient (most commonly available)
            'gemini-1.5-pro',        # More capable
        ]
        
        # If we found an available model from listing, try it first
        if available_model_hint and available_model_hint not in model_names:
            model_names.insert(0, available_model_hint)
        
        response = None
        last_error = None
        successful_model = None
        
        for model_name in model_names:
            try:
                # Create model instance
                model = genai.GenerativeModel(model_name)
                
                # Generate response using Gemini API with the resume text string
                response = model.generate_content(prompt)
                
                # Check if response has text
                if hasattr(response, 'text') and response.text:
                    successful_model = model_name
                    break  # Success, exit loop
                else:
                    raise Exception("Empty response from model")
                    
            except Exception as e:
                error_str = str(e)
                last_error = error_str
                # Continue to try next model
                continue
        
        if response is None or not hasattr(response, 'text') or not response.text:
            # Provide helpful error message
            error_msg = f"Failed to generate response from Gemini API.\n"
            error_msg += f"Tried models: {', '.join(model_names)}\n"
            error_msg += f"Last error: {last_error}\n\n"
            error_msg += "Please check:\n"
            error_msg += "1. Your API key is valid and has access to Gemini models\n"
            error_msg += "2. Your API key has not exceeded quota\n"
            error_msg += "3. The model names are correct for your API version"
            raise Exception(error_msg)
        
        response_text = response.text.strip()

        # Clean up response (remove markdown code blocks if present)
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        response_text = response_text.strip()

        # Parse JSON response
        try:
            ai_data = json.loads(response_text)
        except json.JSONDecodeError as json_err:
            # If JSON parsing fails, return raw response for debugging
            return JsonResponse({
                "error": "AI response parsing failed",
                "raw_response": response_text[:1000],
                "json_error": str(json_err),
                "resume_text_preview": resume_text[:200]  # Show first 200 chars for debugging
            }, status=500)

        # Store analysis in session and redirect to results page
        request.session['ai_analysis'] = ai_data
        request.session['analysis_timestamp'] = str(datetime.now())
        
        return JsonResponse({
            "success": True,
            "redirect_url": "/ai/analysis-results/"
        })

    except Exception as e:
        import traceback
        error_details = {
            "error": f"Error processing resume: {str(e)}",
        }
        if settings.DEBUG:
            error_details["traceback"] = traceback.format_exc()
        return JsonResponse(error_details, status=500)


@login_required
def profile(request):
    """
    Display user profile with all their resumes.
    """
    resumes = Resume.objects.filter(user=request.user).order_by('-created_at')
    
    context = {
        'user': request.user,
        'resumes': resumes,
        'total_resumes': resumes.count(),
    }
    
    return render(request, 'profile.html', context)


@login_required
def ai_analysis_results(request):
    """
    Display the AI resume analysis results on a user-friendly page.
    """
    # Get analysis from session
    ai_data = request.session.get('ai_analysis')
    
    if not ai_data:
        # If no analysis in session, redirect to dashboard
        return redirect('dashboard')
    
    # Clear the session data after retrieving (optional, for security)
    # request.session.pop('ai_analysis', None)
    
    context = {
        'analysis': ai_data,
        'top_companies': ai_data.get('top_companies', []),
        'study_plan': ai_data.get('study_plan', {}),
    }
    
    return render(request, 'ai_analysis_results.html', context)
