import importlib.util
import pypdf
import docx
import re
from io import BytesIO
from pathlib import Path

def _parser_corpus_skill_keywords():
    """Load corpus lexicon without importing the heavy utils package __init__."""
    try:
        path = Path(__file__).resolve().parent / "resume_corpus_insights.py"
        spec = importlib.util.spec_from_file_location("_resume_corpus_insights", path)
        mod = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(mod)
        lex = mod.get_corpus_skill_lexicon()
        return [
            t
            for t in lex
            if len(t) <= 22 and t.count(" ") <= 1 and t.isascii()
        ][:180]
    except Exception:
        return []


class ResumeParser:
    def __init__(self):
        pass
        
    def extract_text_from_pdf(self, pdf_file):
        try:
            # Handle different file input types
            if hasattr(pdf_file, 'read'):
                # If it's a file-like object
                file_content = pdf_file.read()
                pdf_file.seek(0)  # Reset file pointer
            else:
                # If it's already bytes
                file_content = pdf_file
                
            pdf_reader = pypdf.PdfReader(BytesIO(file_content))
            text = ""
            for page in pdf_reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
                else:
                    # Handle empty page text
                    text += "\n"
            return text.strip()
        except Exception as e:
            print(f"Error extracting text from PDF: {e}")
            return ""
            
    def extract_text_from_docx(self, docx_file):
        try:
            doc = docx.Document(BytesIO(docx_file.read()))
            text = ""
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
            return text.strip()
        except Exception as e:
            print(f"Error extracting text from DOCX: {e}")
            return ""
            
    def extract_text(self, file):
        # Reset file pointer to beginning
        file.seek(0)
        
        if file.name.endswith('.pdf'):
            return self.extract_text_from_pdf(file)
        elif file.name.endswith('.docx'):
            return self.extract_text_from_docx(file)
        else:
            return ""
            
    def parse(self, file):
        text = self.extract_text(file)
        
        # Simple keyword-based parsing
        skills = []
        experience = []
        education = []
        
        # Common programming languages and tools + corpus-derived terms (DB / Excel export)
        skill_keywords = [
            'python', 'java', 'javascript', 'html', 'css', 'sql', 'react', 'angular', 'vue',
            'node', 'express', 'django', 'flask', 'spring', 'docker', 'kubernetes', 'aws',
            'azure', 'git', 'jenkins', 'jira',
        ]
        extra = _parser_corpus_skill_keywords()
        skill_keywords = sorted(set(skill_keywords) | set(extra))

        # Look for skills
        text_lower = text.lower()
        for skill in skill_keywords:
            if skill in text_lower:
                skills.append(skill)
                
        return {
            "skills": skills,
            "experience": experience,
            "education": education,
            "raw_text": text
        }