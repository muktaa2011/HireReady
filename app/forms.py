from django import forms
from .models import Resume


class ResumeForm(forms.ModelForm):
    class Meta:
        model = Resume
        exclude = ["user", "created_at", "ats_score", "analyzed"]

        widgets = {
            "full_name": forms.TextInput(attrs={"class": "form-input"}),
            "email": forms.EmailInput(attrs={"class": "form-input"}),
            "mobile": forms.TextInput(attrs={"class": "form-input"}),
            "linkedin": forms.URLInput(attrs={"class": "form-input"}),
            "career_objective": forms.Textarea(attrs={"class": "form-input", "rows": 4}),
            
            # Hidden; values supplied by the dynamic education table
            "edu_qualification": forms.HiddenInput(),
            "edu_year": forms.HiddenInput(),
            "edu_college": forms.HiddenInput(),
            "edu_university": forms.HiddenInput(),
            "edu_cgpa": forms.HiddenInput(),
            "edu_class": forms.HiddenInput(),
            # Hidden; values supplied by dynamic list rows
            "skills": forms.HiddenInput(),
            "projects": forms.HiddenInput(),
            "achievements": forms.HiddenInput(),
            "certifications": forms.HiddenInput(),
            "languages": forms.HiddenInput(),
            "hobbies": forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make photo optional
        self.fields['photo'].required = False

        # Education and list-style fields are filled via JS; allow empty to avoid validation bounce
        for key in [
            "edu_qualification",
            "edu_year",
            "edu_college",
            "edu_university",
            "edu_cgpa",
            "edu_class",
            "skills",
            "projects",
            "achievements",
            "certifications",
            "languages",
            "hobbies",
        ]:
            if key in self.fields:
                self.fields[key].required = False

    def clean_photo(self):
        photo = self.cleaned_data.get("photo")
        if photo:
            if photo.content_type not in ["image/jpeg", "image/png"]:
                raise forms.ValidationError("Only JPG, JPEG or PNG images allowed")
        return photo
