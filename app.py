"""
Hire Sense AI - Main Application
"""
import os

try:
    import bootstrap_env  # noqa: F401 — local: .env + TLS defaults before utils / gRPC
except ModuleNotFoundError:
    pass  # Streamlit Cloud / clones without bootstrap_env.py (file may be gitignored)

import time
try:
    from PIL import Image
except ImportError:
    Image = None
from jobs.job_search import render_job_search
from datetime import datetime
from ui_components import (
    apply_modern_styles, hero_section, feature_card, about_section,
    page_header, render_analytics_section, render_activity_section,
    render_suggestions_section
)
from feedback.feedback import FeedbackManager
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt
from docx import Document
import io
import base64
import plotly.graph_objects as go
from streamlit_lottie import st_lottie
import requests
from dashboard.dashboard import DashboardManager
from config.courses import COURSES_BY_CATEGORY, RESUME_VIDEOS, INTERVIEW_VIDEOS, get_courses_for_role, get_category_for_role
from config.job_roles import JOB_ROLES
from config.database import (
    get_database_connection, save_resume_data, save_analysis_data,
    init_database, ensure_initial_admin, verify_admin, log_admin_action, save_ai_analysis_data,
    get_ai_analysis_stats, reset_ai_analysis_stats, get_detailed_ai_analysis_stats
)
from utils.ai_resume_analyzer import AIResumeAnalyzer
from utils.resume_builder import ResumeBuilder
from utils.resume_analyzer import ResumeAnalyzer
from utils.oauth_login import (
    any_oauth_configured,
    oauth_redirect_uri,
    google_oauth_configured,
    github_oauth_configured,
    google_client_credentials,
    github_client_credentials,
    new_oauth_state,
    build_google_authorize_url,
    build_github_authorize_url,
    exchange_google_code,
    exchange_github_code,
    fetch_google_profile,
    fetch_github_user,
    fetch_github_primary_email,
    normalize_google_user,
    normalize_github_user,
)
import traceback
import plotly.express as px
import pandas as pd
import json
import streamlit as st
import streamlit.components.v1 as components

# Set page config at the very beginning
st.set_page_config(
    page_title="Hire Sense AI",
    page_icon="🚀",
    layout="wide"
)


class ResumeApp:
    def __init__(self):
        """Initialize the application"""
        if 'form_data' not in st.session_state:
            st.session_state.form_data = {
                'personal_info': {
                    'full_name': '',
                    'email': '',
                    'phone': '',
                    'location': '',
                    'linkedin': '',
                    'portfolio': ''
                },
                'summary': '',
                'experiences': [],
                'education': [],
                'projects': [],
                'skills_categories': {
                    'technical': [],
                    'soft': [],
                    'languages': [],
                    'tools': []
                }
            }

        # Initialize navigation state
        if 'page' not in st.session_state:
            st.session_state.page = 'home'

        # Initialize admin state
        if 'is_admin' not in st.session_state:
            st.session_state.is_admin = False

        self.pages = {
            "HOME": self.render_home,
            "RESUME ANALYZER": self.render_analyzer,
            "RESUME BUILDER": self.render_builder,
            "DASHBOARD": self.render_dashboard,
            "JOB SEARCH": self.render_job_search,
            "FEEDBACK": self.render_feedback_page,
            "ℹ ABOUT": self.render_about
        }

        # Initialize dashboard manager
        self.dashboard_manager = DashboardManager()

        self.analyzer = ResumeAnalyzer()
        self.ai_analyzer = AIResumeAnalyzer()
        self.builder = ResumeBuilder()
        self.job_roles = JOB_ROLES

        # Initialize session state
        if 'user_id' not in st.session_state:
            st.session_state.user_id = 'default_user'
        if 'selected_role' not in st.session_state:
            st.session_state.selected_role = None

        if "oauth_user" not in st.session_state:
            st.session_state.oauth_user = None
        if "oauth_browsing_guest" not in st.session_state:
            st.session_state.oauth_browsing_guest = False
        if "oauth_login_step_google" not in st.session_state:
            st.session_state.oauth_login_step_google = False
        if "oauth_login_step_github" not in st.session_state:
            st.session_state.oauth_login_step_github = False

        # Initialize database
        init_database()
        # Streamlit Cloud (and any fresh clone): resume_data.db is not in git — seed admin from app secrets once.
        try:
            if "admin_email" in st.secrets and "admin_password" in st.secrets:
                ensure_initial_admin(
                    str(st.secrets["admin_email"]).strip(),
                    str(st.secrets["admin_password"]),
                )
        except Exception:
            pass

        # Load external CSS
        with open('style/style.css') as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

        # Load Google Fonts
        st.markdown("""
            <link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700&family=Poppins:wght@400;500;600&display=swap" rel="stylesheet">
            <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.4/css/all.min.css">
        """, unsafe_allow_html=True)

        if 'resume_data' not in st.session_state:
            st.session_state.resume_data = []
        if 'ai_analysis_stats' not in st.session_state:
            st.session_state.ai_analysis_stats = {
                'score_distribution': {},
                'total_analyses': 0,
                'average_score': 0
            }

    def load_lottie_url(self, url: str):
        """Load Lottie animation from URL"""
        r = requests.get(url)
        if r.status_code != 200:
            return None
        return r.json()

    def apply_global_styles(self):
        theme = st.session_state.get('theme', 'dark')
        try:
            config_theme = st.get_option('theme.base')
            if config_theme in ('dark', 'light'):
                theme = config_theme
        except Exception:
            pass

        # Keep session state in sync with Streamlit theme settings
        st.session_state.theme = theme
        theme_class = 'theme-dark' if theme == 'dark' else 'theme-light'

        _hire_oauth_login = bool(st.session_state.get("_hire_ui_oauth_login", False))
        _hire_oauth_js = "true" if _hire_oauth_login else "false"
        # All pages (including login) now share the same B/W + green-glow button style
        _oauth_ui_css = ""
        _stmain_link_blue_css = ""

        st.markdown(f"""
        <style>
        :root.theme-dark {{
            --bg: #121212;
            --bg-secondary: #1e1e1e;
            --background-dark: #121212;
            --background-mid: #1e1e1e;
            --background-light: #2d2d2d;
            --sidebar-bg: #1a1a1a;
            --sidebar-border: #333333;
            --card-bg: #1e1e1e;
            --card-border: #333333;
            --text: #e0e0e0;              /* Light gray, good contrast */
            --text-primary: #ffffff;       /* Pure white for important text */
            --text-contrast: #000000;
            --muted: #aaaaaa;              /* Muted text, still readable */

            --primary-color: #2196F3;
            --primary-dark: #1976D2;
            --primary-light: #64B5F6;
            --primary-gradient: linear-gradient(135deg, #2196F3, #1976D2);
            --accent: #2196F3;
            --accent-strong: #1976D2;
            --neon: rgba(33,150,243,0.4);

            --glass: rgba(30,30,30,0.9);
            --glass-border: rgba(255,255,255,0.1);
            --shadow: 0 4px 12px rgba(0,0,0,0.5);
            --button-bg: linear-gradient(135deg, #2196F3, #1976D2);
            --button-hover: linear-gradient(135deg, #42a5f5, #1565C0);
            --button-text: #ffffff;
            --button-hover-text: #ffffff;
            --button-border: 1px solid rgba(129, 199, 132, 0.55);
            --button-hover-shadow: 0 6px 26px rgba(165, 214, 167, 0.55), 0 0 0 2px rgba(129, 199, 132, 0.5), 0 0 28px rgba(102, 187, 106, 0.45);
            --input-bg: #2d2d2d;
        }}

        :root.theme-light {{
            --bg: #f8f9fa;
            --bg-secondary: #ffffff;
            --background-dark: #f8f9fa;
            --background-mid: #ffffff;
            --background-light: #ffffff;
            --sidebar-bg: #ffffff;
            --sidebar-border: #e0e0e0;
            --card-bg: #ffffff;
            --card-border: #e0e0e0;
            --text: #212121;
            --text-primary: #212121;
            --text-contrast: #ffffff;
            --muted: #757575;

            --primary-color: #2196F3;
            --primary-dark: #1976D2;
            --primary-light: #64B5F6;
            --primary-gradient: linear-gradient(135deg, #2196F3, #1976D2);
            --accent: #2196F3;
            --accent-strong: #1976D2;
            --neon: rgba(33,150,243,0.4);

            --glass: rgba(255,255,255,0.9);
            --glass-border: rgba(255,255,255,0.3);
            --shadow: 0 4px 12px rgba(0,0,0,0.1);
            --button-bg: linear-gradient(135deg, #2196F3, #1976D2);
            --button-hover: linear-gradient(135deg, #42a5f5, #1565C0);
            --button-text: #ffffff;
            --button-hover-text: #ffffff;
            --button-border: 1px solid rgba(102, 187, 106, 0.65);
            --button-hover-shadow: 0 8px 28px rgba(165, 214, 167, 0.65), 0 0 0 2px rgba(129, 199, 132, 0.55), 0 0 32px rgba(129, 199, 132, 0.4);
            --input-bg: #ffffff;

        }}

        html {{
            scroll-behavior: smooth;
        }}

        body {{
            background: var(--bg);
            color: var(--text);
            font-family: 'Inter', sans-serif;
            transition: background 0.35s ease, color 0.35s ease;
        }}

        .stApp {{
            background: var(--bg) !important;
            color: var(--text) !important;
        }}

        /* Force sidebar to follow theme color */
        .css-1d391kg, .css-1d391kg::-webkit-scrollbar-track {{
            background: var(--sidebar-bg) !important;
        }}

        .css-1d391kg .stButton button,
        .css-1d391kg [data-testid="stButton"] button {{
            background: var(--button-bg) !important;
            background-image: var(--button-bg) !important;
            background-color: var(--primary-dark) !important;
            color: var(--button-text) !important;
            -webkit-text-fill-color: var(--button-text) !important;
            border: 2px solid rgba(102, 187, 106, 0.65) !important;
            box-shadow: 0 2px 14px rgba(129, 199, 132, 0.4), 0 6px 18px rgba(0,0,0,0.14) !important;
            transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease !important;
        }}

        .css-1d391kg .stButton button:hover,
        .css-1d391kg [data-testid="stButton"] button:hover {{
            transform: translateY(-6px) !important;
            background: var(--button-hover) !important;
            background-image: var(--button-hover) !important;
            color: var(--button-hover-text) !important;
            -webkit-text-fill-color: var(--button-hover-text) !important;
            border-color: rgba(129, 199, 132, 0.95) !important;
            box-shadow: var(--button-hover-shadow), 0 8px 22px rgba(0,0,0,0.12) !important;
        }}

        /* Improve heading contrast */
        .header-title, .hero-header .header-title {{
            color: var(--text) !important;               /* fallback */
            background: var(--primary-gradient) !important;
            -webkit-background-clip: text !important;
            -webkit-text-fill-color: transparent !important;
            background-clip: text !important;
            text-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}

        .header-subtitle, .hero-header .header-subtitle {{
            color: var(--text) !important;
        }}

        .main {{
            background: var(--glass) !important;
            border: 1px solid var(--glass-border) !important;
            border-radius: 20px;
            padding: 2rem;
            margin: 1.5rem auto;
            max-width: 1200px;
            box-shadow: var(--shadow);
            backdrop-filter: blur(16px);
        }}

        .stCard {{
            background: var(--glass) !important;
            border: 1px solid var(--glass-border) !important;
            border-radius: 18px;
            padding: 1.8rem;
            box-shadow: var(--shadow);
            transition: transform 0.25s ease, box-shadow 0.25s ease;
            backdrop-filter: blur(14px);
        }}

        /* Ensure common component wrappers follow the selected theme */
        .page-header, .hero-header, .feature-card {{
            background: var(--background-mid) !important;
            border: 1px solid var(--glass-border) !important;
            color: var(--text) !important;
        }}

        .page-header .header-title, .hero-header .header-title {{
            color: var(--text) !important;
            -webkit-text-fill-color: var(--text) !important;
        }}

        .page-header .header-subtitle, .hero-header .header-subtitle {{
            color: var(--text) !important;
        }}

        .stCard:hover {{
            transform: translateY(-6px);
            box-shadow: 0 20px 48px rgba(0,0,0,0.45);
            animation: neonPulse 4s ease-in-out infinite;
        }}

        /* ========== Universal B/W + green-glow button style (matches login page) ========== */
        .stButton button,
        [data-testid="stButton"] button,
        div[data-testid^="stBaseButton"] button,
        div[data-testid="stDownloadButton"] button {{
            transform: translateY(0) !important;
            background: #ffffff !important;
            background-image: none !important;
            background-color: #ffffff !important;
            color: #111111 !important;
            -webkit-text-fill-color: #111111 !important;
            border: 2px solid #1a1a1a !important;
            padding: 0.9rem 1.7rem !important;
            border-radius: 18px !important;
            font-weight: 700 !important;
            text-transform: uppercase;
            letter-spacing: 1.1px;
            cursor: pointer !important;
            box-shadow: 0 2px 10px rgba(0,0,0,0.06) !important;
            transition: transform 0.2s ease, box-shadow 0.2s ease, background-color 0.2s ease, border-color 0.2s ease !important;
            opacity: 1 !important;
        }}

        .stButton button:hover,
        [data-testid="stButton"] button:hover,
        div[data-testid^="stBaseButton"] button:hover,
        div[data-testid="stDownloadButton"] button:hover {{
            transform: translateY(-6px) !important;
            background: #f4f4f4 !important;
            background-image: none !important;
            background-color: #f4f4f4 !important;
            color: #000000 !important;
            -webkit-text-fill-color: #000000 !important;
            border-color: #1a1a1a !important;
            box-shadow: 0 14px 36px rgba(129, 199, 132, 0.45), 0 0 0 2px rgba(165, 214, 167, 0.75), 0 6px 20px rgba(76, 175, 80, 0.2) !important;
            animation: none;
        }}

        /* Link buttons (same B/W style) */
        [data-testid="stLinkButton"] a,
        a[data-testid^="stLinkButton"],
        div[data-testid="stLinkButton"] a {{
            display: block !important;
            text-align: center !important;
            text-decoration: none !important;
            box-sizing: border-box !important;
            padding: 0.85rem 1.5rem !important;
            border-radius: 18px !important;
            font-weight: 700 !important;
            text-transform: uppercase;
            letter-spacing: 1.1px;
            background: #ffffff !important;
            background-image: none !important;
            background-color: #ffffff !important;
            color: #111111 !important;
            -webkit-text-fill-color: #111111 !important;
            border: 2px solid #1a1a1a !important;
            box-shadow: 0 2px 10px rgba(0,0,0,0.06) !important;
            transition: transform 0.2s ease, box-shadow 0.2s ease, background-color 0.2s ease, border-color 0.2s ease !important;
        }}
        [data-testid="stLinkButton"] a:hover,
        a[data-testid^="stLinkButton"]:hover,
        div[data-testid="stLinkButton"] a:hover {{
            transform: translateY(-6px) !important;
            background: #f4f4f4 !important;
            background-image: none !important;
            background-color: #f4f4f4 !important;
            color: #000000 !important;
            -webkit-text-fill-color: #000000 !important;
            border-color: #1a1a1a !important;
            box-shadow: 0 14px 36px rgba(129, 199, 132, 0.45), 0 0 0 2px rgba(165, 214, 167, 0.75), 0 6px 20px rgba(76, 175, 80, 0.2) !important;
        }}

        .stTextInput > div > div {{
            background: var(--input-bg);
            border: 1px solid rgba(255,255,255,0.18);
            border-radius: 18px;
            color: var(--text);
            box-shadow: inset 0 4px 10px rgba(0,0,0,0.25);
            backdrop-filter: blur(10px);
        }}

        .stTextInput > div > div:focus-within {{
            border-color: var(--accent);
            box-shadow: 0 0 0 1px var(--accent), inset 0 4px 12px rgba(0,0,0,0.25);
        }}

        /* Custom Scrollbar */
        ::-webkit-scrollbar {{
            width: 10px;
            height: 10px;
        }}

        ::-webkit-scrollbar-track {{
            background: rgba(255,255,255,0.03);
            border-radius: 10px;
        }}

        ::-webkit-scrollbar-thumb {{
            background: rgba(62,220,151,0.6);
            border-radius: 10px;
            border: 2px solid transparent;
            background-clip: content-box;
        }}

        ::-webkit-scrollbar-thumb:hover {{
            background: rgba(62,220,151,0.9);
        }}

        /* ========== DASHBOARD PAGE FIXES ========== */
        .dashboard-container,
        .dashboard-section,
        .analytics-grid,
        .stat-card,
        .metric-card,
        .activity-list,
        .suggestions-list,
        .activity-item,
        .suggestion-item,
        .dashboard-section h3,
        .stat-card h4,
        .stat-number,
        .activity-item p,
        .suggestion-item p,
        .activity-time,
        .skill-tag span {{
            color: var(--text-primary) !important;
        }}

        /* Ensure stat numbers (which may use gradient) keep their gradient */
        .stat-number {{
            background: var(--primary-gradient) !important;
            -webkit-background-clip: text !important;
            -webkit-text-fill-color: transparent !important;
            background-clip: text !important;
        }}

        /* ========== FEEDBACK PAGE FIXES ========== */
        .feedback-section,
        .feedback-card,
        .feedback-item,
        .feedback-header,
        .feedback-content,
        .feedback-description,
        .feedback-category,
        .feedback-container,
        .stTextArea textarea,
        .stTextArea textarea::placeholder,
        .stSlider label,
        .stSlider span {{
            color: var(--text-primary) !important;
        }}

        .stTextArea textarea {{
            background-color: var(--input-bg) !important;
            border-color: var(--card-border) !important;
        }}

        /* Placeholder text in feedback form */
        .stTextArea textarea::placeholder {{
            color: var(--muted) !important;
            opacity: 1;
        }}

        @keyframes neonPulse {{
            0%, 100% {{
                box-shadow: 0 0 0 rgba(0,0,0,0), 0 0 0 rgba(0,0,0,0);
            }}
            50% {{
                box-shadow: 0 0 25px var(--neon), 0 0 45px rgba(0,0,0,0.15);
            }}
        }}


        /* ========== Sidebar explicit reinforcement (inherits global B/W) ========== */
        [data-testid="stSidebar"] .stButton button,
        [data-testid="stSidebar"] [data-testid="stButton"] button,
        [data-testid="stSidebar"] button[data-testid^="stBaseButton"],
        [data-testid="stSidebar"] [data-testid^="stBaseButton"] button,
        [data-testid="stSidebar"] div[data-testid^="stBaseButton"] button {{
            background: #ffffff !important;
            background-image: none !important;
            background-color: #ffffff !important;
            color: #111111 !important;
            -webkit-text-fill-color: #111111 !important;
            border: 2px solid #1a1a1a !important;
            box-shadow: 0 2px 12px rgba(0,0,0,0.06), 0 0 0 1px rgba(26,26,26,0.08) !important;
            transition: transform 0.2s ease, box-shadow 0.2s ease, background-color 0.2s ease, border-color 0.2s ease !important;
        }}
        [data-testid="stSidebar"] .stButton button:hover,
        [data-testid="stSidebar"] [data-testid="stButton"] button:hover,
        [data-testid="stSidebar"] button[data-testid^="stBaseButton"]:hover,
        [data-testid="stSidebar"] [data-testid^="stBaseButton"] button:hover,
        [data-testid="stSidebar"] div[data-testid^="stBaseButton"] button:hover {{
            transform: translateY(-5px) !important;
            background: #f4f4f4 !important;
            background-image: none !important;
            background-color: #f4f4f4 !important;
            color: #000000 !important;
            -webkit-text-fill-color: #000000 !important;
            border-color: #1a1a1a !important;
            box-shadow: 0 14px 36px rgba(129, 199, 132, 0.45), 0 0 0 2px rgba(165, 214, 167, 0.75), 0 6px 20px rgba(76, 175, 80, 0.2) !important;
        }}

        /* legacy hash-based sidebar class fallback */
        .css-1d391kg .stButton button,
        .css-1d391kg [data-testid="stButton"] button {{
            background: #ffffff !important;
            background-image: none !important;
            background-color: #ffffff !important;
            color: #111111 !important;
            -webkit-text-fill-color: #111111 !important;
            border: 2px solid #1a1a1a !important;
            box-shadow: 0 2px 12px rgba(0,0,0,0.06) !important;
            transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease !important;
        }}
        .css-1d391kg .stButton button:hover,
        .css-1d391kg [data-testid="stButton"] button:hover {{
            transform: translateY(-5px) !important;
            background: #f4f4f4 !important;
            background-image: none !important;
            color: #000000 !important;
            -webkit-text-fill-color: #000000 !important;
            border-color: #1a1a1a !important;
            box-shadow: 0 14px 36px rgba(129, 199, 132, 0.45), 0 0 0 2px rgba(165, 214, 167, 0.75), 0 6px 20px rgba(76, 175, 80, 0.2) !important;
        }}
        </style>
        <script>
            const themeClass = '{theme_class}';
            document.documentElement.classList.remove('theme-dark', 'theme-light');
            document.documentElement.classList.add(themeClass);
            const HIRE_OAUTH_LOGIN = {_hire_oauth_js};
            if (HIRE_OAUTH_LOGIN) {{
                document.body.dataset.hireUi = 'oauth-login';
            }} else {{
                delete document.body.dataset.hireUi;
            }}

            (function hireSenseStreamlitButtons() {{
                // Universal B/W + green-glow constants (same as login page)
                const BG_COLOR = '#ffffff';
                const BG_HOVER = '#f4f4f4';
                const TEXT_COLOR = '#111111';
                const BORDER = '2px solid #1a1a1a';
                const SHADOW = '0 2px 10px rgba(0,0,0,0.06)';
                const SHADOW_H = '0 14px 36px rgba(129, 199, 132, 0.45), 0 0 0 2px rgba(165, 214, 167, 0.75), 0 6px 20px rgba(76, 175, 80, 0.2)';

                function skipWidget(btn) {{
                    if (btn.getAttribute('role') === 'tab') return true;
                    const skip = ['stFileUploader','stDateInput','stTimeInput','stNumberInput','stColorPicker','stCameraInput'];
                    for (const id of skip) {{
                        if (btn.closest('[data-testid="' + id + '"]')) return true;
                    }}
                    return false;
                }}

                function isStreamlitActionButton(btn) {{
                    if (skipWidget(btn)) return false;
                    const tid = btn.getAttribute('data-testid') || '';
                    if (tid.indexOf('stBaseButton') === 0) return true;
                    if (btn.closest('[data-testid^="stBaseButton"]')) return true;
                    if (btn.closest('[data-testid="stButton"]')) return true;
                    if (btn.closest('.stButton')) return true;
                    if (btn.matches('button[kind="primary"]') || btn.matches('button[kind="secondary"]')) return true;
                    const inScope = btn.closest('section[data-testid="stMain"], section.main, [data-testid="stSidebar"]');
                    if (inScope) {{
                        const r = btn.getBoundingClientRect();
                        if (r.width >= 96 && r.height >= 30) return true;
                    }}
                    return false;
                }}

                function paintButtons() {{
                    document.querySelectorAll('.stApp button').forEach((btn) => {{
                        if (!isStreamlitActionButton(btn)) return;
                        btn.style.setProperty('background-image', 'none', 'important');
                        btn.style.setProperty('background-color', BG_COLOR, 'important');
                        btn.style.setProperty('color', TEXT_COLOR, 'important');
                        btn.style.setProperty('-webkit-text-fill-color', TEXT_COLOR, 'important');
                        btn.style.setProperty('border', BORDER, 'important');
                        btn.style.setProperty('box-shadow', SHADOW, 'important');
                        btn.style.setProperty('transform', 'translateY(0)', 'important');
                    }});
                    document.querySelectorAll('[data-testid="stLinkButton"] a, a[data-testid^="stLinkButton"]').forEach((a) => {{
                        a.style.setProperty('background-image', 'none', 'important');
                        a.style.setProperty('background-color', BG_COLOR, 'important');
                        a.style.setProperty('color', TEXT_COLOR, 'important');
                        a.style.setProperty('-webkit-text-fill-color', TEXT_COLOR, 'important');
                        a.style.setProperty('border', BORDER, 'important');
                        a.style.setProperty('box-shadow', SHADOW, 'important');
                        a.style.setProperty('text-decoration', 'none', 'important');
                        a.style.setProperty('transform', 'translateY(0)', 'important');
                    }});
                }}

                function addHoverListeners() {{
                    document.querySelectorAll('.stApp button').forEach((btn) => {{
                        if (!isStreamlitActionButton(btn) || btn.dataset.hireSenseHover) return;
                        btn.dataset.hireSenseHover = '1';
                        btn.addEventListener('mouseenter', () => {{
                            btn.style.setProperty('background-color', BG_HOVER, 'important');
                            btn.style.setProperty('box-shadow', SHADOW_H, 'important');
                            btn.style.setProperty('transform', 'translateY(-6px)', 'important');
                        }});
                        btn.addEventListener('mouseleave', () => {{
                            btn.style.setProperty('background-color', BG_COLOR, 'important');
                            btn.style.setProperty('box-shadow', SHADOW, 'important');
                            btn.style.setProperty('transform', 'translateY(0)', 'important');
                        }});
                    }});
                    document.querySelectorAll('[data-testid="stLinkButton"] a, a[data-testid^="stLinkButton"]').forEach((a) => {{
                        if (a.dataset.hireSenseHover) return;
                        a.dataset.hireSenseHover = '1';
                        a.addEventListener('mouseenter', () => {{
                            a.style.setProperty('background-color', BG_HOVER, 'important');
                            a.style.setProperty('box-shadow', SHADOW_H, 'important');
                            a.style.setProperty('transform', 'translateY(-6px)', 'important');
                        }});
                        a.addEventListener('mouseleave', () => {{
                            a.style.setProperty('background-color', BG_COLOR, 'important');
                            a.style.setProperty('box-shadow', SHADOW, 'important');
                            a.style.setProperty('transform', 'translateY(0)', 'important');
                        }});
                    }});
                }}

                let t = null;
                function tick() {{
                    paintButtons();
                    addHoverListeners();
                }}
                function schedule() {{
                    clearTimeout(t);
                    t = setTimeout(tick, 60);
                }}

                tick();
                requestAnimationFrame(() => requestAnimationFrame(tick));
                new MutationObserver(schedule).observe(document.body, {{ childList: true, subtree: true }});
            }})();
        </script>
        """, unsafe_allow_html=True)

    def add_footer(self):
        """Add a footer to all pages"""
        st.markdown("<hr style='margin-top: 50px; margin-bottom: 20px;'>", unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns([1, 3, 1])
        
        with col2:
            # GitHub star button with lottie animation
            st.markdown("""
            <div style='display: flex; justify-content: center; align-items: center; margin-bottom: 10px;'>
                <a href='https://github.com/VALIBOYINA-MURALI-SAI/Hiresense_AI' target='_blank' style='text-decoration: none;'>
                    <div style='display: flex; align-items: center; background-color: var(--card-bg); border: 1px solid var(--card-border); padding: 5px 10px; border-radius: 5px; transition: all 0.3s ease;'>
                        <svg height="16" width="16" viewBox="0 0 16 16" version="1.1" style='margin-right: 5px;'>
                            <path fill-rule="evenodd" d="M8 .25a.75.75 0 01.673.418l1.882 3.815 4.21.612a.75.75 0 01.416 1.279l-3.046 2.97.719 4.192a.75.75 0 01-1.088.791L8 12.347l-3.766 1.98a.75.75 0 01-1.088-.79l.72-4.194L.818 6.374a.75.75 0 01.416-1.28l4.21-.611L7.327.668A.75.75 0 018 .25z" fill="gold"></path>
                        </svg>
                        <span style='color: var(--text); font-size: 14px;'>Star this repo</span>
                    </div>
                </a>
            </div>
            """, unsafe_allow_html=True)
            
            # Footer text
            st.markdown("""
            <p style='text-align: center;'>
                Powered by <b>Streamlit</b> and <b>Google Gemini AI</b> | Developed by 
                <a href="https://www.linkedin.com/in/valiboyina-murali-sai-ba5689250/" target="_blank" style='text-decoration: none; color: var(--text)'>
                    <b>Murali Sai & Omkar</b>
                </a>
            </p>
            <p style='text-align: center; font-size: 12px; color: var(--muted);'>
                "Every star counts! If you find this project helpful, please consider starring the repo to help it reach more people."
            </p>
            """, unsafe_allow_html=True)

    def load_image(self, image_name):
        """Load image from static directory"""
        try:
            image_path = f"c:/Users/shree/Downloads/smart-resume-ai/{image_name}"
            with open(image_path, "rb") as f:
                image_bytes = f.read()
            encoded = base64.b64encode(image_bytes).decode()
            return f"data:image/png;base64,{encoded}"
        except Exception as e:
            print(f"Error loading image {image_name}: {e}")
            return None

    def export_to_excel(self):
        """Export resume data to Excel"""
        conn = get_database_connection()

        # Get resume data with analysis
        query = """
            SELECT
                rd.name, rd.email, rd.phone, rd.linkedin, rd.github, rd.portfolio,
                rd.summary, rd.target_role, rd.target_category,
                rd.education, rd.experience, rd.projects, rd.skills,
                ra.ats_score, ra.keyword_match_score, ra.format_score, ra.section_score,
                ra.missing_skills, ra.recommendations,
                rd.created_at
            FROM resume_data rd
            LEFT JOIN resume_analysis ra ON rd.id = ra.resume_id
        """

        try:
            # Read data into DataFrame
            df = pd.read_sql_query(query, conn)

            # Create Excel writer object
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Resume Data')

            return output.getvalue()
        except Exception as e:
            print(f"Error exporting to Excel: {str(e)}")
            return None
        finally:
            conn.close()

    def render_dashboard(self):
        """Render the dashboard page"""
        self.dashboard_manager.render_dashboard()

        st.toast("Check out these repositories: [Awesome Hacking](https://github.com/VALIBOYINA-MURALI-SAI/Hiresense_AI)", icon="ℹ️")


    def render_empty_state(self, icon, message):
        """Render an empty state with icon and message"""
        return f"""
            <div style='text-align: center; padding: 2rem; color: var(--muted);'>
                <i class='{icon}' style='font-size: 2rem; margin-bottom: 1rem; color: var(--accent);'></i>
                <p style='margin: 0;'>{message}</p>
            </div>
        """

    def analyze_resume(self, resume_text):
        """Analyze resume and store results"""
        analytics = self.analyzer.analyze_resume(resume_text)
        st.session_state.analytics_data = analytics
        return analytics

    def handle_resume_upload(self):
        """Handle resume upload and analysis"""
        uploaded_file = st.file_uploader(
            "Upload your resume", type=['pdf', 'docx'])

        if uploaded_file is not None:
            try:
                # Extract text from resume
                if uploaded_file.type == "application/pdf":
                    resume_text = self.analyzer.extract_text_from_pdf(uploaded_file)
                else:
                    resume_text = self.analyzer.extract_text_from_docx(uploaded_file)

                # Store resume data
                st.session_state.resume_data = {
                    'filename': uploaded_file.name,
                    'content': resume_text,
                    'upload_time': datetime.now().isoformat()
                }

                # Analyze resume
                analytics = self.analyze_resume(resume_text)

                return True
            except Exception as e:
                st.error(f"Error processing resume: {str(e)}")
                return False
        return False

    def render_builder(self):
        st.title("Resume Builder 📝")
        st.write("Create your professional resume")

        # Template selection
        template_options = ["Modern", "Professional", "Minimal", "Creative"]
        selected_template = st.selectbox(
    "Select Resume Template", template_options)
        st.success(f"🎨 Currently using: {selected_template} Template")

        # Personal Information
        st.subheader("Personal Information")

        col1, col2 = st.columns(2)
        with col1:
            # Get existing values from session state
            existing_name = st.session_state.form_data['personal_info']['full_name']
            existing_email = st.session_state.form_data['personal_info']['email']
            existing_phone = st.session_state.form_data['personal_info']['phone']

            # Input fields with existing values
            full_name = st.text_input("Full Name", value=existing_name)
            email = st.text_input(
    "Email",
    value=existing_email,
     key="email_input")
            phone = st.text_input("Phone", value=existing_phone)

            # Immediately update session state after email input
            if 'email_input' in st.session_state:
                st.session_state.form_data['personal_info']['email'] = st.session_state.email_input

        with col2:
            # Get existing values from session state
            existing_location = st.session_state.form_data['personal_info']['location']
            existing_linkedin = st.session_state.form_data['personal_info']['linkedin']
            existing_portfolio = st.session_state.form_data['personal_info']['portfolio']

            # Input fields with existing values
            location = st.text_input("Location", value=existing_location)
            linkedin = st.text_input("LinkedIn URL", value=existing_linkedin)
            portfolio = st.text_input(
    "Portfolio Website", value=existing_portfolio)

        # Update personal info in session state
        st.session_state.form_data['personal_info'] = {
            'full_name': full_name,
            'email': email,
            'phone': phone,
            'location': location,
            'linkedin': linkedin,
            'portfolio': portfolio
        }

        # Professional Summary
        st.subheader("Professional Summary")
        summary = st.text_area("Professional Summary", value=st.session_state.form_data.get('summary', ''), height=150,
                             help="Write a brief summary highlighting your key skills and experience")

        # Experience Section
        st.subheader("Work Experience")
        if 'experiences' not in st.session_state.form_data:
            st.session_state.form_data['experiences'] = []

        if st.button("Add Experience"):
            st.session_state.form_data['experiences'].append({
                'company': '',
                'position': '',
                'start_date': '',
                'end_date': '',
                'description': '',
                'responsibilities': [],
                'achievements': []
            })

        for idx, exp in enumerate(st.session_state.form_data['experiences']):
            with st.expander(f"Experience {idx + 1}", expanded=True):
                col1, col2 = st.columns(2)
                with col1:
                    exp['company'] = st.text_input(
    "Company Name",
    key=f"company_{idx}",
    value=exp.get(
        'company',
         ''))
                    exp['position'] = st.text_input(
    "Position", key=f"position_{idx}", value=exp.get(
        'position', ''))
                with col2:
                    exp['start_date'] = st.text_input(
    "Start Date", key=f"start_date_{idx}", value=exp.get(
        'start_date', ''))
                    exp['end_date'] = st.text_input(
    "End Date", key=f"end_date_{idx}", value=exp.get(
        'end_date', ''))

                exp['description'] = st.text_area("Role Overview", key=f"desc_{idx}",
                                                value=exp.get(
                                                    'description', ''),
                                                help="Brief overview of your role and impact")

                # Responsibilities
                st.markdown("##### Key Responsibilities")
                resp_text = st.text_area("Enter responsibilities (one per line)",
                                       key=f"resp_{idx}",
                                       value='\n'.join(
                                           exp.get('responsibilities', [])),
                                       height=100,
                                       help="List your main responsibilities, one per line")
                exp['responsibilities'] = [r.strip()
                                                   for r in resp_text.split('\n') if r.strip()]

                # Achievements
                st.markdown("##### Key Achievements")
                achv_text = st.text_area("Enter achievements (one per line)",
                                       key=f"achv_{idx}",
                                       value='\n'.join(
                                           exp.get('achievements', [])),
                                       height=100,
                                       help="List your notable achievements, one per line")
                exp['achievements'] = [a.strip()
                                               for a in achv_text.split('\n') if a.strip()]

                if st.button("Remove Experience", key=f"remove_exp_{idx}"):
                    st.session_state.form_data['experiences'].pop(idx)
                    st.rerun()

        # Projects Section
        st.subheader("Projects")
        if 'projects' not in st.session_state.form_data:
            st.session_state.form_data['projects'] = []

        if st.button("Add Project"):
            st.session_state.form_data['projects'].append({
                'name': '',
                'technologies': '',
                'description': '',
                'responsibilities': [],
                'achievements': [],
                'link': ''
            })

        for idx, proj in enumerate(st.session_state.form_data['projects']):
            with st.expander(f"Project {idx + 1}", expanded=True):
                proj['name'] = st.text_input(
    "Project Name",
    key=f"proj_name_{idx}",
    value=proj.get(
        'name',
         ''))
                proj['technologies'] = st.text_input("Technologies Used", key=f"proj_tech_{idx}",
                                                   value=proj.get(
                                                       'technologies', ''),
                                                   help="List the main technologies, frameworks, and tools used")

                proj['description'] = st.text_area("Project Overview", key=f"proj_desc_{idx}",
                                                 value=proj.get(
                                                     'description', ''),
                                                 help="Brief overview of the project and its goals")

                # Project Responsibilities
                st.markdown("##### Key Responsibilities")
                proj_resp_text = st.text_area("Enter responsibilities (one per line)",
                                            key=f"proj_resp_{idx}",
                                            value='\n'.join(
                                                proj.get('responsibilities', [])),
                                            height=100,
                                            help="List your main responsibilities in the project")
                proj['responsibilities'] = [r.strip()
                                                    for r in proj_resp_text.split('\n') if r.strip()]

                # Project Achievements
                st.markdown("##### Key Achievements")
                proj_achv_text = st.text_area("Enter achievements (one per line)",
                                            key=f"proj_achv_{idx}",
                                            value='\n'.join(
                                                proj.get('achievements', [])),
                                            height=100,
                                            help="List the project's key achievements and your contributions")
                proj['achievements'] = [a.strip()
                                                for a in proj_achv_text.split('\n') if a.strip()]

                proj['link'] = st.text_input("Project Link (optional)", key=f"proj_link_{idx}",
                                           value=proj.get('link', ''),
                                           help="Link to the project repository, demo, or documentation")

                if st.button("Remove Project", key=f"remove_proj_{idx}"):
                    st.session_state.form_data['projects'].pop(idx)
                    st.rerun()

        # Education Section
        st.subheader("Education")
        if 'education' not in st.session_state.form_data:
            st.session_state.form_data['education'] = []

        if st.button("Add Education"):
            st.session_state.form_data['education'].append({
                'school': '',
                'degree': '',
                'field': '',
                'graduation_date': '',
                'gpa': '',
                'achievements': []
            })

        for idx, edu in enumerate(st.session_state.form_data['education']):
            with st.expander(f"Education {idx + 1}", expanded=True):
                col1, col2 = st.columns(2)
                with col1:
                    edu['school'] = st.text_input(
    "School/University",
    key=f"school_{idx}",
    value=edu.get(
        'school',
         ''))
                    edu['degree'] = st.text_input(
    "Degree", key=f"degree_{idx}", value=edu.get(
        'degree', ''))
                with col2:
                    edu['field'] = st.text_input(
    "Field of Study",
    key=f"field_{idx}",
    value=edu.get(
        'field',
         ''))
                    edu['graduation_date'] = st.text_input("Graduation Date", key=f"grad_date_{idx}",
                                                         value=edu.get('graduation_date', ''))

                edu['gpa'] = st.text_input(
    "GPA (optional)",
    key=f"gpa_{idx}",
    value=edu.get(
        'gpa',
         ''))

                # Educational Achievements
                st.markdown("##### Achievements & Activities")
                edu_achv_text = st.text_area("Enter achievements (one per line)",
                                           key=f"edu_achv_{idx}",
                                           value='\n'.join(
                                               edu.get('achievements', [])),
                                           height=100,
                                           help="List academic achievements, relevant coursework, or activities")
                edu['achievements'] = [a.strip()
                                               for a in edu_achv_text.split('\n') if a.strip()]

                if st.button("Remove Education", key=f"remove_edu_{idx}"):
                    st.session_state.form_data['education'].pop(idx)
                    st.rerun()

        # Skills Section
        st.subheader("Skills")
        if 'skills_categories' not in st.session_state.form_data:
            st.session_state.form_data['skills_categories'] = {
                'technical': [],
                'soft': [],
                'languages': [],
                'tools': []
            }

        col1, col2 = st.columns(2)
        with col1:
            tech_skills = st.text_area("Technical Skills (one per line)",
                                     value='\n'.join(
    st.session_state.form_data['skills_categories']['technical']),
                                     height=150,
                                     help="Programming languages, frameworks, databases, etc.")
            st.session_state.form_data['skills_categories']['technical'] = [
                s.strip() for s in tech_skills.split('\n') if s.strip()]

            soft_skills = st.text_area("Soft Skills (one per line)",
                                     value='\n'.join(
    st.session_state.form_data['skills_categories']['soft']),
                                     height=150,
                                     help="Leadership, communication, problem-solving, etc.")
            st.session_state.form_data['skills_categories']['soft'] = [
                s.strip() for s in soft_skills.split('\n') if s.strip()]

        with col2:
            languages = st.text_area("Languages (one per line)",
                                   value='\n'.join(
    st.session_state.form_data['skills_categories']['languages']),
                                   height=150,
                                   help="Programming or human languages with proficiency level")
            st.session_state.form_data['skills_categories']['languages'] = [
                l.strip() for l in languages.split('\n') if l.strip()]

            tools = st.text_area("Tools & Technologies (one per line)",
                               value='\n'.join(
    st.session_state.form_data['skills_categories']['tools']),
                               height=150,
                               help="Development tools, software, platforms, etc.")
            st.session_state.form_data['skills_categories']['tools'] = [
                t.strip() for t in tools.split('\n') if t.strip()]

        # Update form data in session state
        st.session_state.form_data.update({
            'summary': summary
        })

        # Generate Resume button
        if st.button("Generate Resume 📄", type="primary"):
            print("Validating form data...")
            print(f"Session state form data: {st.session_state.form_data}")
            print(f"Email input value: {st.session_state.get('email_input', '')}")

            # Get the current values from form
            current_name = st.session_state.form_data['personal_info']['full_name'].strip()
            current_email = st.session_state.email_input if 'email_input' in st.session_state else ''

            print(f"Current name: {current_name}")
            print(f"Current email: {current_email}")

            # Validate required fields
            if not current_name:
                st.error("⚠️ Please enter your full name.")

            if not current_email:
                st.error("⚠️ Please enter your email address.")

            # Update email in form data one final time
            st.session_state.form_data['personal_info']['email'] = current_email

            try:
                print("Preparing resume data...")
                # Prepare resume data with current form values
                resume_data = {
                    "personal_info": st.session_state.form_data['personal_info'],
                    "summary": st.session_state.form_data.get('summary', '').strip(),
                    "experience": st.session_state.form_data.get('experiences', []),
                    "education": st.session_state.form_data.get('education', []),
                    "projects": st.session_state.form_data.get('projects', []),
                    "skills": st.session_state.form_data.get('skills_categories', {
                        'technical': [],
                        'soft': [],
                        'languages': [],
                        'tools': []
                    }),
                    "template": selected_template
                }

                print(f"Resume data prepared: {resume_data}")

                try:
                    # Generate resume
                    resume_buffer = self.builder.generate_resume(resume_data)
                    if resume_buffer:
                        try:
                            # Save resume data to database
                            save_resume_data(resume_data)

                            # Offer the resume for download
                            st.success("✅ Resume generated successfully!")

                            # Show snowflake effect
                            st.snow()

                            st.download_button(
                                label="Download Resume 📥",
                                data=resume_buffer,
                                file_name=f"{current_name.replace(' ', '_')}_resume.docx",
                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                on_click=lambda: st.balloons()
                            )
                        except Exception as db_error:
                            print(f"Warning: Failed to save to database: {str(db_error)}")
                            # Still allow download even if database save fails
                            st.warning(
                                "⚠️ Resume generated but couldn't be saved to database")
                            
                            # Show balloons effect
                            st.balloons()

                            st.download_button(
                                label="Download Resume 📥",
                                data=resume_buffer,
                                file_name=f"{current_name.replace(' ', '_')}_resume.docx",
                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                on_click=lambda: st.balloons()
                            )
                    else:
                        st.error(
                            "❌ Failed to generate resume. Please try again.")
                        print("Resume buffer was None")
                except Exception as gen_error:
                    print(f"Error during resume generation: {str(gen_error)}")
                    print(f"Full traceback: {traceback.format_exc()}")
                    st.error(f"❌ Error generating resume: {str(gen_error)}")

            except Exception as e:
                print(f"Error preparing resume data: {str(e)}")
                print(f"Full traceback: {traceback.format_exc()}")
                st.error(f"❌ Error preparing resume data: {str(e)}")

        st.toast("Check out these repositories: [30-Days-Of-Rust](https://github.com/VALIBOYINA-MURALI-SAI/Hiresense_AI)", icon="ℹ️")

    def render_about(self):
        """Render the about page"""
        # Apply modern styles
        from ui_components import apply_modern_styles
        import base64
        import os

        # Function to load image as base64
        def get_image_as_base64(file_path):
            try:
                with open(file_path, "rb") as image_file:
                    encoded = base64.b64encode(image_file.read()).decode()
                    return f"data:image/jpeg;base64,{encoded}"
            except:
                return None

        # Get image path and convert to base64
        image_path = os.path.join(
    os.path.dirname(__file__),
    "assets",
     "Logo.jpeg")
        image_base64 = get_image_as_base64(image_path)

        apply_modern_styles()

        # Add Font Awesome icons and custom CSS
        about_css = """
            <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
            <style>
                .profile-section, .vision-section, .feature-card {
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    text-align: center;
                    padding: 2rem;
                    background: var(--background-mid);
                    color: var(--text);
                    border-radius: 20px;
                    margin: 2rem auto;
                    max-width: 800px;
                }

                .profile-image {
                    width: 200px;
                    height: 200px;
                    border-radius: 50%;
                    margin: 0 auto 1.5rem;
                    display: block;
                    object-fit: cover;
                    border: 4px solid var(--accent);
                }

                .profile-name {
                    font-size: 2.5rem;
                    color: var(--text);
                    margin-bottom: 0.5rem;
                }

                .profile-title {
                    font-size: 1.2rem;
                    color: var(--accent);
                }

                .social-links {
                    display: flex;
                    justify-content: center;
                    gap: 1.5rem;
                    margin: 2rem 0;
                }

                .social-link {
                    font-size: 2rem;
                    color: var(--accent);
                    transition: all 0.3s ease;
                    padding: 0.5rem;
                    border-radius: 50%;
                    background: rgba(33, 150, 243, 0.15);
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    text-decoration: none;
                }

                .social-link:hover {
                    transform: translateY(-5px);
                    background: var(--accent);
                    color: var(--text-contrast);
                    box-shadow: 0 5px 15px rgba(33, 150, 243, 0.35);
                }

                .bio-text {
                    color: var(--muted);
                    line-height: 1.8;
                    font-size: 1.1rem;
                    margin-top: 2rem;
                    text-align: left;
                }

                .vision-text {
                    color: var(--muted);
                    line-height: 1.8;
                    font-size: 1.1rem;
                    font-style: italic;
                    margin: 1.5rem 0;
                    text-align: left;
                }

                .vision-icon {
                    font-size: 2.5rem;
                    color: var(--accent);
                    margin-bottom: 1rem;
                }

                .vision-title {
                    font-size: 2rem;
                    color: var(--text);
                    margin-bottom: 1rem;
                }

                .features-grid {
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                    gap: 2rem;
                    margin: 2rem auto;
                    max-width: 1200px;
                }

                .feature-card {
                    padding: 2rem;
                    margin: 0;
                }

                .feature-icon {
                    font-size: 2.5rem;
                    color: var(--accent);
                    margin-bottom: 1rem;
                }

                .feature-title {
                    font-size: 1.5rem;
                    color: var(--text);
                    margin: 1rem 0;
                }

                .feature-description {
                    color: var(--muted);
                    line-height: 1.6;
                }
            </style>
        """
        st.markdown(about_css, unsafe_allow_html=True)

        # Hero Section
        st.markdown("""
            <div class="hero-section">
                <h1 class="hero-title">About Hire Sense AI</h1>
                <p class="hero-subtitle">A powerful AI-driven platform for optimizing your resume</p>
            </div>
        """, unsafe_allow_html=True)

        # Profile Section
        st.markdown(f"""
            <div class="profile-section">
                <img src="{image_base64 if image_base64 else 'https://github.com/VALIBOYINA-MURALI-SAI/Hiresense_AI'}"
                     alt="Murali Sai & Omkar"
                     class="profile-image"
                     onerror="this.onerror=null; this.src='https://github.com/VALIBOYINA-MURALI-SAI/Hiresense_AI';">
                <h2 class="profile-name">Murali Sai & Omkar</h2>
                <p class="profile-title">Full Stack Developer & AI/ML Enthusiast</p>
                <div class="social-links">
                    <a href="https://github.com/VALIBOYINA-MURALI-SAI/Hiresense_AI" class="social-link" target="_blank">
                        <i class="fab fa-github"></i>
                    </a>
                    <a href="https://www.linkedin.com/in/valiboyina-murali-sai-ba5689250/" class="social-link" target="_blank">
                        <i class="fab fa-linkedin"></i>
                    </a>
                    <a href="mailto:valiboinamuralisai@gmail.com" class="social-link" target="_blank">
                        <i class="fas fa-envelope"></i>
                    </a>
                </div>
                <p class="bio-text">
                    Hello! I'm a passionate Full Stack Developer with expertise in AI and Machine Learning.
                    I created Hire Sense AI to revolutionize how job seekers approach their career journey.
                    With my background in both software development and AI, I've designed this platform to
                    provide intelligent, data-driven insights for resume optimization.
                </p>
            </div>
        """, unsafe_allow_html=True)




        # Vision Section
        st.markdown("""
            <div class="vision-section">
                <i class="fas fa-lightbulb vision-icon"></i>
                <h2 class="vision-title">Our Vision</h2>
                <p class="vision-text">
                    "Hire Sense AI represents my vision of democratizing career advancement through technology.
                    By combining cutting-edge AI with intuitive design, this platform empowers job seekers at
                    every career stage to showcase their true potential and stand out in today's competitive job market."
                </p>
            </div>
        """, unsafe_allow_html=True)

        # Features Section
        st.markdown("""
            <div class="features-grid">
                <div class="feature-card">
                    <i class="fas fa-robot feature-icon"></i>
                    <h3 class="feature-title">AI-Powered Analysis</h3>
                    <p class="feature-description">
                        Advanced AI algorithms provide detailed insights and suggestions to optimize your resume for maximum impact.
                    </p>
                </div>
                <div class="feature-card">
                    <i class="fas fa-chart-line feature-icon"></i>
                    <h3 class="feature-title">Data-Driven Insights</h3>
                    <p class="feature-description">
                        Make informed decisions with our analytics-based recommendations and industry insights.
                    </p>
                </div>
                <div class="feature-card">
                    <i class="fas fa-shield-alt feature-icon"></i>
                    <h3 class="feature-title">Privacy First</h3>
                    <p class="feature-description">
                        Your data security is our priority. We ensure your information is always protected and private.
                    </p>
                </div>
            </div>
            <div style="text-align: center; margin: 3rem 0;">
                <a href="?page=analyzer" class="cta-button">
                    Start Your Journey
                    <i class="fas fa-arrow-right" style="margin-left: 10px;"></i>
                </a>
            </div>
        """, unsafe_allow_html=True)

        st.toast("Check out these repositories: [Iriswise](https://github.com/VALIBOYINA-MURALI-SAI/Hiresense_AI)", icon="ℹ️")

    def render_analyzer(self):
        """Render the resume analyzer page"""
        apply_modern_styles()

        # Page Header
        page_header(
            "Resume Analyzer",
            "Get instant AI-powered feedback to optimize your resume"
        )

        # Create tabs for Normal Analyzer and AI Analyzer
        analyzer_tabs = st.tabs(["Standard Analyzer", "AI Analyzer"])

        with analyzer_tabs[0]:
            # Job Role Selection
            categories = list(self.job_roles.keys())
            selected_category = st.selectbox(
    "Job Category", categories, key="standard_category")

            roles = list(self.job_roles[selected_category].keys())
            selected_role = st.selectbox(
    "Specific Role", roles, key="standard_role")

            role_info = self.job_roles[selected_category][selected_role]

            # Display role information
            st.markdown(f"""
            <div style='background-color: var(--card-bg); padding: 20px; border-radius: 10px; margin: 10px 0; border: 1px solid var(--card-border); color: var(--text);'>
                <h3 style='color: var(--text);'>{selected_role}</h3>
                <p style='color: var(--text);'>{role_info['description']}</p>
                <h4 style='color: var(--text);'>Required Skills:</h4>
                <p style='color: var(--text);'>{', '.join(role_info['required_skills'])}</p>
            </div>
            """, unsafe_allow_html=True)

            # File Upload
            uploaded_file = st.file_uploader(
    "Upload your resume", type=[
        'pdf', 'docx'], key="standard_file")

            if not uploaded_file:
                # Display empty state with a prominent upload button
                st.markdown(
                    self.render_empty_state(
                    "fas fa-cloud-upload-alt",
                    "Upload your resume to get started with standard analysis"
                    ),
                    unsafe_allow_html=True
                )
                # Add a prominent upload button
                col1, col2, col3 = st.columns([1, 2, 1])
                with col2:
                    st.markdown("""
                    <style>
                    .upload-button {
                        background: var(--primary-gradient);
                        color: var(--text-contrast);
                        border: none;
                        border-radius: 10px;
                        padding: 15px 25px;
                        font-size: 18px;
                        font-weight: bold;
                        cursor: pointer;
                        width: 100%;
                        text-align: center;
                        margin: 20px 0;
                        box-shadow: 0 4px 10px rgba(0,0,0,0.2);
                        transition: all 0.3s ease;
                    }
                    .upload-button:hover {
                        transform: translateY(-3px);
                        box-shadow: 0 6px 15px rgba(0,0,0,0.3);
                    }

                    """, unsafe_allow_html=True)

            if uploaded_file:
                # Add a prominent analyze button
                analyze_standard = st.button("🔍 Analyze My Resume",
                                    type="primary",
                                    use_container_width=True,
                                    key="analyze_standard_button")

                if analyze_standard:
                    with st.spinner("Analyzing your document..."):
                        # Get file content
                        text = ""
                        try:
                            if uploaded_file.type == "application/pdf":
                                try:
                                    text = self.analyzer.extract_text_from_pdf(uploaded_file)
                                except Exception as pdf_error:
                                    st.error(f"PDF extraction failed: {str(pdf_error)}")
                                    st.info("Trying alternative PDF extraction method...")
                                    # Try AI analyzer as backup
                                    try:
                                        text = self.ai_analyzer.extract_text_from_pdf(uploaded_file)
                                    except Exception as backup_error:
                                        st.error(f"All PDF extraction methods failed: {str(backup_error)}")
                                        return
                            elif uploaded_file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
                                try:
                                    text = self.analyzer.extract_text_from_docx(uploaded_file)
                                except Exception as docx_error:
                                    st.error(f"DOCX extraction failed: {str(docx_error)}")
                                    # Try AI analyzer as backup
                                    try:
                                        text = self.ai_analyzer.extract_text_from_docx(uploaded_file)
                                    except Exception as backup_error:
                                        st.error(f"All DOCX extraction methods failed: {str(backup_error)}")
                                        return
                            else:
                                text = uploaded_file.getvalue().decode()
                                
                            if not text or text.strip() == "":
                                st.error("Could not extract any text from the uploaded file. Please try a different file.")
                                return
                        except Exception as e:
                            st.error(f"Error reading file: {str(e)}")
                            return

                        # Analyze the document (target_role enables Excel corpus skill priors)
                        job_requirements = {
                            **role_info,
                            "target_role": selected_role,
                            "target_category": selected_category,
                        }
                        analysis = self.analyzer.analyze_resume(
                            {"raw_text": text}, job_requirements
                        )
                        
                        # Check if analysis returned an error
                        if 'error' in analysis:
                            st.error(analysis['error'])
                            return

                        # Show snowflake effect
                        st.snow()

                        # Save resume data to database
                        resume_data = {
                            'personal_info': {
                                'name': analysis.get('name', ''),
                                'email': analysis.get('email', ''),
                                'phone': analysis.get('phone', ''),
                                'linkedin': analysis.get('linkedin', ''),
                                'github': analysis.get('github', ''),
                                'portfolio': analysis.get('portfolio', '')
                            },
                            'summary': analysis.get('summary', ''),
                            'target_role': selected_role,
                            'target_category': selected_category,
                            'education': analysis.get('education', []),
                            'experience': analysis.get('experience', []),
                            'projects': analysis.get('projects', []),
                            'skills': analysis.get('skills', []),
                            'template': ''
                        }

                        # Save to database
                        try:
                            resume_id = save_resume_data(resume_data)

                            # Save analysis data
                            analysis_data = {
                                'resume_id': resume_id,
                                'ats_score': analysis['ats_score'],
                                'keyword_match_score': analysis['keyword_match']['score'],
                                'format_score': analysis['format_score'],
                                'section_score': analysis['section_score'],
                                'missing_skills': ','.join(analysis['keyword_match']['missing_skills']),
                                'recommendations': ','.join(analysis['suggestions'])
                            }
                            save_analysis_data(resume_id, analysis_data)
                            st.success("Resume data saved successfully!")
                        except Exception as e:
                            st.error(f"Error saving to database: {str(e)}")
                            print(f"Database error: {e}")

                        # Show results based on document type
                        if analysis.get('document_type') != 'resume':
                            st.error(f"⚠️ This appears to be a {analysis['document_type']} document, not a resume!")
                            st.warning(
                                "Please upload a proper resume for ATS analysis.")
                            return
                        # Display results in a modern card layout
                    col1, col2 = st.columns(2)

                    with col1:
                        # ATS Score Card with circular progress
                        st.markdown("""
                        <div class="feature-card">
                            <h2>ATS Score</h2>
                            <div style="position: relative; width: 150px; height: 150px; margin: 0 auto;">
                                <div style="
                                    position: absolute;
                                    width: 150px;
                                    height: 150px;
                                    border-radius: 50%;
                                    background: conic-gradient(
                                        #4CAF50 0% {score}%,
                                        #2c2c2c {score}% 100%
                                    );
                                    display: flex;
                                    align-items: center;
                                    justify-content: center;
                                ">
                                    <div style="
                                        width: 120px;
                                        height: 120px;
                                        background: #1a1a1a;
                                        border-radius: 50%;
                                        display: flex;
                                        align-items: center;
                                        justify-content: center;
                                        font-size: 24px;
                                        font-weight: bold;
                                        color: {color};
                                    ">
                                        {score}
                                    </div>
                                </div>
                            </div>
                            <div style="text-align: center; margin-top: 10px;">
                                <span style="
                                    font-size: 1.2em;
                                    color: {color};
                                    font-weight: bold;
                                ">
                                    {status}
                                </span>
                            </div>
                        """.format(
                            score=analysis['ats_score'],
                            color='#4CAF50' if analysis['ats_score'] >= 80 else '#FFA500' if analysis[
                                'ats_score'] >= 60 else '#FF4444',
                            status='Excellent' if analysis['ats_score'] >= 80 else 'Good' if analysis[
                                'ats_score'] >= 60 else 'Needs Improvement'
                        ), unsafe_allow_html=True)

                        st.markdown("</div>", unsafe_allow_html=True)

                        # self.display_analysis_results(analysis_results)

                        # Skills Match Card
                        st.markdown("""
                        <div class="feature-card">
                            <h2>Skills Match</h2>
                        """, unsafe_allow_html=True)

                        st.metric(
                            "Keyword Match", f"{int(analysis.get('keyword_match', {}).get('score', 0))}%")
                        _km = analysis.get("keyword_match", {})
                        if _km.get("corpus_priors_added"):
                            _meta = _km.get("corpus_prior_meta") or {}
                            _mr = _meta.get("matched_corpus_role") or selected_role
                            st.caption(
                                f"Skills checklist includes **{len(_km['corpus_priors_added'])}** extra terms "
                                f"from your export data for roles like “{_mr}”: "
                                f"{', '.join(_km['corpus_priors_added'][:10])}"
                                + (" …" if len(_km["corpus_priors_added"]) > 10 else "")
                            )

                        if analysis['keyword_match']['missing_skills']:
                            st.markdown("#### Missing Skills:")
                            for skill in analysis['keyword_match']['missing_skills']:
                                st.markdown(f"- {skill}")

                        st.markdown("</div>", unsafe_allow_html=True)

                    with col2:
                        # Format Score Card
                        st.markdown("""
                        <div class="feature-card">
                            <h2>Format Analysis</h2>
                        """, unsafe_allow_html=True)

                        st.metric("Format Score",
                                  f"{int(analysis.get('format_score', 0))}%")
                        st.metric("Section Score",
                                  f"{int(analysis.get('section_score', 0))}%")

                        st.markdown("</div>", unsafe_allow_html=True)

                        # Suggestions Card with improved UI
                        st.markdown("""
                        <div class="feature-card">
                            <h2>📋 Resume Improvement Suggestions</h2>
                        """, unsafe_allow_html=True)

                            # Contact Section
                        if analysis.get('contact_suggestions'):
                                st.markdown("""
                                <div style='background-color: var(--card-bg); border: 1px solid var(--card-border); padding: 15px; border-radius: 10px; margin: 10px 0; color: var(--text);'>
                                    <h3 style='color: var(--accent); margin-bottom: 10px;'>📞 Contact Information</h3>
                                    <ul style='list-style-type: none; padding-left: 0;'>
                                """, unsafe_allow_html=True)
                                for suggestion in analysis.get(
                                    'contact_suggestions', []):
                                    st.markdown(
    f"<li style='margin-bottom: 8px;'>✓ {suggestion}</li>",
     unsafe_allow_html=True)
                                st.markdown(
    "</ul></div>", unsafe_allow_html=True)

                            # Summary Section
                        if analysis.get('summary_suggestions'):
                                st.markdown("""
                                <div style='background-color: var(--card-bg); border: 1px solid var(--card-border); padding: 15px; border-radius: 10px; margin: 10px 0; color: var(--text);'>
                                    <h3 style='color: var(--accent); margin-bottom: 10px;'>📝 Professional Summary</h3>
                                    <ul style='list-style-type: none; padding-left: 0;'>
                                """, unsafe_allow_html=True)
                                for suggestion in analysis.get(
                                    'summary_suggestions', []):
                                    st.markdown(
    f"<li style='margin-bottom: 8px;'>✓ {suggestion}</li>",
     unsafe_allow_html=True)
                                st.markdown(
    "</ul></div>", unsafe_allow_html=True)

                            # Skills Section
                        if analysis.get(
                            'skills_suggestions') or analysis['keyword_match']['missing_skills']:
                                st.markdown("""
                                <div style='background-color: var(--card-bg); border: 1px solid var(--card-border); padding: 15px; border-radius: 10px; margin: 10px 0; color: var(--text);'>
                                    <h3 style='color: var(--accent); margin-bottom: 10px;'>🎯 Skills</h3>
                                    <ul style='list-style-type: none; padding-left: 0;'>
                                """, unsafe_allow_html=True)
                                for suggestion in analysis.get(
                                    'skills_suggestions', []):
                                    st.markdown(
    f"<li style='margin-bottom: 8px;'>✓ {suggestion}</li>",
     unsafe_allow_html=True)
                                if analysis['keyword_match']['missing_skills']:
                                    st.markdown(
    "<li style='margin-bottom: 8px;'>✓ Consider adding these relevant skills:</li>",
     unsafe_allow_html=True)
                                    for skill in analysis['keyword_match']['missing_skills']:
                                        st.markdown(
    f"<li style='margin-left: 20px; margin-bottom: 4px;'>• {skill}</li>",
     unsafe_allow_html=True)
                                st.markdown(
    "</ul></div>", unsafe_allow_html=True)

                            # Experience Section
                        if analysis.get('experience_suggestions'):
                                st.markdown("""
                                <div style='background-color: var(--card-bg); border: 1px solid var(--card-border); padding: 15px; border-radius: 10px; margin: 10px 0; color: var(--text);'>
                                    <h3 style='color: var(--accent); margin-bottom: 10px;'>💼 Work Experience</h3>
                                    <ul style='list-style-type: none; padding-left: 0;'>
                                """, unsafe_allow_html=True)
                                for suggestion in analysis.get(
                                    'experience_suggestions', []):
                                    st.markdown(
    f"<li style='margin-bottom: 8px;'>✓ {suggestion}</li>",
     unsafe_allow_html=True)
                                st.markdown(
    "</ul></div>", unsafe_allow_html=True)

                            # Education Section
                        if analysis.get('education_suggestions'):
                                st.markdown("""
                                <div style='background-color: var(--card-bg); border: 1px solid var(--card-border); padding: 15px; border-radius: 10px; margin: 10px 0; color: var(--text);'>
                                    <h3 style='color: var(--accent); margin-bottom: 10px;'>🎓 Education</h3>
                                    <ul style='list-style-type: none; padding-left: 0;'>
                                """, unsafe_allow_html=True)
                                for suggestion in analysis.get(
                                    'education_suggestions', []):
                                    st.markdown(
    f"<li style='margin-bottom: 8px;'>✓ {suggestion}</li>",
     unsafe_allow_html=True)
                                st.markdown(
    "</ul></div>", unsafe_allow_html=True)

                            # General Formatting Suggestions
                        if analysis.get('format_suggestions'):
                                st.markdown("""
                                <div style='background-color: var(--card-bg); border: 1px solid var(--card-border); padding: 15px; border-radius: 10px; margin: 10px 0; color: var(--text);'>
                                    <h3 style='color: var(--accent); margin-bottom: 10px;'>📄 Formatting</h3>
                                    <ul style='list-style-type: none; padding-left: 0;'>
                                """, unsafe_allow_html=True)
                                for suggestion in analysis.get(
                                    'format_suggestions', []):
                                    st.markdown(
    f"<li style='margin-bottom: 8px;'>✓ {suggestion}</li>",
     unsafe_allow_html=True)
                                st.markdown(
    "</ul></div>", unsafe_allow_html=True)

                        st.markdown("</div>", unsafe_allow_html=True)

                        # Course Recommendations
                    st.markdown("""
                        <div class="feature-card">
                            <h2>📚 Recommended Courses</h2>
                        """, unsafe_allow_html=True)

                        # Get courses based on role and category
                    courses = get_courses_for_role(selected_role)
                    if not courses:
                            category = get_category_for_role(selected_role)
                            courses = COURSES_BY_CATEGORY.get(
                                category, {}).get(selected_role, [])

                        # Display courses in a grid
                    cols = st.columns(2)
                    for i, course in enumerate(
                        courses[:6]):  # Show top 6 courses
                            with cols[i % 2]:
                                st.markdown(f"""
                                <div style='background-color: var(--card-bg); border: 1px solid var(--card-border); padding: 15px; border-radius: 10px; margin: 10px 0; color: var(--text);'>
                                    <h4 style='color: var(--text);'>{course[0]}</h4>
                                    <a href='{course[1]}' target='_blank' style='color: var(--accent);'>View Course</a>
                                </div>
                                """, unsafe_allow_html=True)

                    st.markdown("</div>", unsafe_allow_html=True)

                        # Learning Resources
                    st.markdown("""
                        <div class="feature-card">
                            <h2>📺 Helpful Videos</h2>
                        """, unsafe_allow_html=True)

                    tab1, tab2 = st.tabs(["Resume Tips", "Interview Tips"])

                    with tab1:
                            # Resume Videos
                            for category, videos in RESUME_VIDEOS.items():
                                st.subheader(category)
                                cols = st.columns(2)
                                for i, video in enumerate(videos):
                                    with cols[i % 2]:
                                        st.video(video[1])

                    with tab2:
                            # Interview Videos
                            for category, videos in INTERVIEW_VIDEOS.items():
                                st.subheader(category)
                                cols = st.columns(2)
                                for i, video in enumerate(videos):
                                    with cols[i % 2]:
                                        st.video(video[1])

                    st.markdown("</div>", unsafe_allow_html=True)

        with analyzer_tabs[1]:
            st.markdown("""
            <div style='background-color: var(--card-bg); border: 1px solid var(--card-border); padding: 20px; border-radius: 10px; margin: 10px 0; color: var(--text);'>
                <h3 style='color: var(--text);'>AI-Powered Resume Analysis</h3>
                <p style='color: var(--text);'>Get detailed insights from advanced AI models that analyze your resume and provide personalized recommendations.</p>
                <p style='color: var(--text);'><strong>Upload your resume to get AI-powered analysis and recommendations.</strong></p>
            </div>
            """, unsafe_allow_html=True)

            # AI Model Selection
            ai_model = st.selectbox(
                "Select AI Model",
                ["Google Gemini"],
                help="Choose the AI model to analyze your resume"
            )
             
            # Add job description input option
            use_custom_job_desc = st.checkbox("Use custom job description", value=False, 
                                             help="Enable this to provide a specific job description for more targeted analysis")
            
            custom_job_description = ""
            if use_custom_job_desc:
                custom_job_description = st.text_area(
                    "Paste the job description here",
                    height=200,
                    placeholder="Paste the full job description from the company here for more targeted analysis...",
                    help="Providing the actual job description will help the AI analyze your resume specifically for this position"
                )
                
                st.markdown("""
                <div style='background-color: var(--accent); padding: 15px; border-radius: 10px; margin: 10px 0; color: var(--button-text);'>
                    <p><i class="fas fa-lightbulb"></i> <strong>Pro Tip:</strong> Including the actual job description significantly improves the accuracy of the analysis and provides more relevant recommendations tailored to the specific position.</p>
                </div>
                """, unsafe_allow_html=True)
             
                        # Add AI Analyzer Stats in an expander
            with st.expander("📊 AI Analyzer Statistics", expanded=False):
                try:
                    # Add a reset button for admin users
                    if st.session_state.get('is_admin', False):
                        if st.button(
    "🔄 Reset AI Analysis Statistics",
    type="secondary",
     key="reset_ai_stats_button_2"):
                            from config.database import reset_ai_analysis_stats
                            result = reset_ai_analysis_stats()
                            if result["success"]:
                                st.success(result["message"])
                            else:
                                st.error(result["message"])
                            # Refresh the page to show updated stats
                            st.experimental_rerun()

                    # Get detailed AI analysis statistics
                    from config.database import get_detailed_ai_analysis_stats
                    ai_stats = get_detailed_ai_analysis_stats()

                    if ai_stats["total_analyses"] > 0:
                        # Create a more visually appealing layout
                        st.markdown("""
                        <style>
                        .stats-card {
                            background: linear-gradient(135deg, #1e3c72, #2a5298);
                            border-radius: 10px;
                            padding: 15px;
                            margin-bottom: 15px;
                            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
                            text-align: center;
                        }
                        .stats-value {
                            font-size: 28px;
                            font-weight: bold;
                            color: var(--text-contrast);
                            margin: 10px 0;
                        }
                        .stats-label {
                            font-size: 14px;
                            color: var(--muted);
                            text-transform: uppercase;
                            letter-spacing: 1px;
                        }
                        .score-card {
                            background: linear-gradient(135deg, #11998e, #38ef7d);
                            border-radius: 10px;
                            padding: 15px;
                            margin-bottom: 15px;
                            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
                            text-align: center;
                        }
                        </style>
                        """, unsafe_allow_html=True)

                        col1, col2, col3 = st.columns(3)

                        with col1:
                            st.markdown(f"""
                            <div class="stats-card">
                                <div class="stats-label">Total AI Analyses</div>
                                <div class="stats-value">{ai_stats["total_analyses"]}</div>
                            </div>
                            """, unsafe_allow_html=True)

                        with col2:
                            # Determine color based on score
                            score_color = "#38ef7d" if ai_stats["average_score"] >= 80 else "#FFEB3B" if ai_stats[
                                "average_score"] >= 60 else "#FF5252"
                            st.markdown(f"""
                            <div class="stats-card" style="background: linear-gradient(135deg, #2c3e50, {score_color});">
                                <div class="stats-label">Average Resume Score</div>
                                <div class="stats-value">{ai_stats["average_score"]}/100</div>
                            </div>
                            """, unsafe_allow_html=True)

                        with col3:
                            # Create a gauge chart for average score
                            import plotly.graph_objects as go
                            chart_text_color = "#F3F7FA" if st.session_state.get('theme', 'dark') == 'dark' else "#111827"
                            fig = go.Figure(go.Indicator(
                                mode="gauge+number",
                                value=ai_stats["average_score"],
                                domain={'x': [0, 1], 'y': [0, 1]},
                                title={
    'text': "Score", 'font': {
        'size': 14, 'color': chart_text_color}},
                                gauge={
                                    'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': chart_text_color},
                                    'bar': {'color': "#38ef7d" if ai_stats["average_score"] >= 80 else "#FFEB3B" if ai_stats["average_score"] >= 60 else "#FF5252"},
                                    'bgcolor': "rgba(0,0,0,0)",
                                    'borderwidth': 2,
                                    'bordercolor': chart_text_color,
                                    'steps': [
                                        {'range': [
                                            0, 40], 'color': 'rgba(255, 82, 82, 0.3)'},
                                        {'range': [
                                            40, 70], 'color': 'rgba(255, 235, 59, 0.3)'},
                                        {'range': [
                                            70, 100], 'color': 'rgba(56, 239, 125, 0.3)'}
                                    ],
                                }
                            ))

                            fig.update_layout(
                                paper_bgcolor='rgba(0,0,0,0)',
                                plot_bgcolor='rgba(0,0,0,0)',
                                font={'color': chart_text_color},
                                height=150,
                                margin=dict(l=10, r=10, t=30, b=10)
                            )

                            st.plotly_chart(fig, use_container_width=True)

                        # Display model usage with enhanced visualization
                        if ai_stats["model_usage"]:
                            st.markdown("### 🤖 Model Usage")
                            model_data = pd.DataFrame(ai_stats["model_usage"])

                            # Create a more colorful pie chart
                            import plotly.express as px
                            fig = px.pie(
                                model_data,
                                values="count",
                                names="model",
                                color_discrete_sequence=px.colors.qualitative.Bold,
                                hole=0.4
                            )

                            fig.update_traces(
                                textposition='inside',
                                textinfo='percent+label',
                                marker=dict(
    line=dict(
        color='#000000',
         width=1.5))
                            )

                            fig.update_layout(
                                margin=dict(l=20, r=20, t=30, b=20),
                                height=300,
                                paper_bgcolor='rgba(0,0,0,0)',
                                plot_bgcolor='rgba(0,0,0,0)',
                                font=dict(color="#ffffff", size=14),
                                legend=dict(
                                    orientation="h",
                                    yanchor="bottom",
                                    y=-0.1,
                                    xanchor="center",
                                    x=0.5
                                ),
                                title={
                                    'text': 'AI Model Distribution',
                                    'y': 0.95,
                                    'x': 0.5,
                                    'xanchor': 'center',
                                    'yanchor': 'top',
                                    'font': {'size': 18, 'color': 'white'}
                                }
                            )

                            st.plotly_chart(fig, use_container_width=True)

                        # Display top job roles with enhanced visualization
                        if ai_stats["top_job_roles"]:
                            st.markdown("### 🎯 Top Job Roles")
                            roles_data = pd.DataFrame(
                                ai_stats["top_job_roles"])

                            # Create a more colorful bar chart
                            fig = px.bar(
                                roles_data,
                                x="role",
                                y="count",
                                color="count",
                                color_continuous_scale=px.colors.sequential.Viridis,
                                labels={
    "role": "Job Role", "count": "Number of Analyses"}
                            )

                            fig.update_traces(
                                marker_line_width=1.5,
                                marker_line_color="white",
                                opacity=0.9
                            )

                            fig.update_layout(
                                margin=dict(l=20, r=20, t=50, b=30),
                                height=350,
                                paper_bgcolor='rgba(0,0,0,0)',
                                plot_bgcolor='rgba(0,0,0,0)',
                                font=dict(color="#ffffff", size=14),
                                title={
                                    'text': 'Most Analyzed Job Roles',
                                    'y': 0.95,
                                    'x': 0.5,
                                    'xanchor': 'center',
                                    'yanchor': 'top',
                                    'font': {'size': 18, 'color': 'white'}
                                },
                                xaxis=dict(
                                    title="",
                                    tickangle=-45,
                                    tickfont=dict(size=12)
                                ),
                                yaxis=dict(
                                    title="Number of Analyses",
                                    gridcolor="rgba(255, 255, 255, 0.1)"
                                ),
                                coloraxis_showscale=False
                            )

                            st.plotly_chart(fig, use_container_width=True)

                            # Add a timeline chart for analysis over time (mock
                            # data for now)
                            st.markdown("### 📈 Analysis Trend")
                            st.info(
                                "This is a conceptual visualization. To implement actual time-based analysis, additional data collection would be needed.")

                            # Create mock data for timeline
                            import datetime
                            import numpy as np

                            today = datetime.datetime.now()
                            dates = [
    (today -
    datetime.timedelta(
        days=i)).strftime('%Y-%m-%d') for i in range(7)]
                            dates.reverse()

                            # Generate some random data that sums to
                            # total_analyses
                            total = ai_stats["total_analyses"]
                            if total > 7:
                                values = np.random.dirichlet(
                                    np.ones(7)) * total
                                values = [round(v) for v in values]
                                # Adjust to make sure sum equals total
                                diff = total - sum(values)
                                values[-1] += diff
                            else:
                                values = [0] * 7
                                for i in range(total):
                                    values[-(i % 7) - 1] += 1

                            trend_data = pd.DataFrame({
                                'Date': dates,
                                'Analyses': values
                            })

                            fig = px.line(
                                trend_data,
                                x='Date',
                                y='Analyses',
                                markers=True,
                                line_shape='spline',
                                color_discrete_sequence=["#38ef7d"]
                            )

                            fig.update_traces(
                                line=dict(width=3),
                                marker=dict(
    size=8, line=dict(
        width=2, color='white'))
                            )

                            fig.update_layout(
                                margin=dict(l=20, r=20, t=50, b=30),
                                height=300,
                                paper_bgcolor='rgba(0,0,0,0)',
                                plot_bgcolor='rgba(0,0,0,0)',
                                font=dict(color="#ffffff", size=14),
                                title={
                                    'text': 'Analysis Activity (Last 7 Days)',
                                    'y': 0.95,
                                    'x': 0.5,
                                    'xanchor': 'center',
                                    'yanchor': 'top',
                                    'font': {'size': 18, 'color': 'white'}
                                },
                                xaxis=dict(
                                    title="",
                                    gridcolor="rgba(255, 255, 255, 0.1)"
                                ),
                                yaxis=dict(
                                    title="Number of Analyses",
                                    gridcolor="rgba(255, 255, 255, 0.1)"
                                )
                            )

                            st.plotly_chart(fig, use_container_width=True)

                        # Display score distribution if available
                        if ai_stats["score_distribution"]:
                            st.markdown("""
                            <h3 style='text-align: center; margin-bottom: 20px; background: linear-gradient(90deg, #4b6cb7, #182848); padding: 15px; border-radius: 10px; color: var(--text); box-shadow: 0 4px 10px rgba(0,0,0,0.2);'>
                                📊 Score Distribution Analysis
                            </h3>
                            """, unsafe_allow_html=True)

                            score_data = pd.DataFrame(
                                ai_stats["score_distribution"])

                            # Create a more visually appealing bar chart for
                            # score distribution
                            fig = px.bar(
                                score_data,
                                x="range",
                                y="count",
                                color="range",
                                color_discrete_map={
                                    "0-20": "#FF5252",
                                    "21-40": "#FF7043",
                                    "41-60": "#FFEB3B",
                                    "61-80": "#8BC34A",
                                    "81-100": "#38ef7d"
                                },
                                labels={
    "range": "Score Range",
     "count": "Number of Resumes"},
                                text="count"  # Display count values on bars
                            )

                            fig.update_traces(
                                marker_line_width=2,
                                marker_line_color="white",
                                opacity=0.9,
                                textposition='outside',
                                textfont=dict(
    color="white", size=14, family="Arial, sans-serif"),
                                hovertemplate="<b>Score Range:</b> %{x}<br><b>Number of Resumes:</b> %{y}<extra></extra>"
                            )

                            # Add a gradient background to the chart
                            fig.update_layout(
                                margin=dict(l=20, r=20, t=50, b=30),
                                height=400,  # Increase height for better visibility
                                paper_bgcolor='rgba(0,0,0,0)',
                                plot_bgcolor='rgba(0,0,0,0)',
                                font=dict(
    color="#ffffff", size=14, family="Arial, sans-serif"),
                                # title={
                                #     # 'text': 'Resume Score Distribution',
                                #     'y': 0.95,
                                #     'x': 0.5,
                                #     'xanchor': 'center',
                                #     'yanchor': 'top',
                                #     'font': {'size': 22, 'color': 'white', 'family': 'Arial, sans-serif', 'weight': 'bold'}
                                # },
                                xaxis=dict(
                                    title=dict(
    text="Score Range", font=dict(
        size=16, color="white")),
                                    categoryorder="array",
                                    categoryarray=[
    "0-20", "21-40", "41-60", "61-80", "81-100"],
                                    tickfont=dict(size=14, color="white"),
                                    gridcolor="rgba(255, 255, 255, 0.1)"
                                ),
                                yaxis=dict(
                                    title=dict(
    text="Number of Resumes", font=dict(
        size=16, color="white")),
                                    tickfont=dict(size=14, color="white"),
                                    gridcolor="rgba(255, 255, 255, 0.1)",
                                    zeroline=False
                                ),
                                showlegend=False,
                                bargap=0.2,  # Adjust gap between bars
                                shapes=[
                                    # Add gradient background
                                    dict(
                                        type="rect",
                                        xref="paper",
                                        yref="paper",
                                        x0=0,
                                        y0=0,
                                        x1=1,
                                        y1=1,
                                        fillcolor="rgba(26, 26, 44, 0.5)",
                                        layer="below",
                                        line_width=0,
                                    )
                                ]
                            )

                            # Add annotations for insights
                            if len(score_data) > 0:
                                max_count_idx = score_data["count"].idxmax()
                                max_range = score_data.iloc[max_count_idx]["range"]
                                max_count = score_data.iloc[max_count_idx]["count"]

                                fig.add_annotation(
                                    x=0.5,
                                    y=1.12,
                                    xref="paper",
                                    yref="paper",
                                    text=f"Most resumes fall in the {max_range} score range",
                                    showarrow=False,
                                    font=dict(size=14, color="#FFEB3B"),
                                    bgcolor="rgba(0,0,0,0.5)",
                                    bordercolor="#FFEB3B",
                                    borderwidth=1,
                                    borderpad=4,
                                    opacity=0.8
                                )

                            # Display the chart in a styled container
                            st.markdown("""
                            <div style='background: linear-gradient(135deg, #1e3c72, #2a5298); padding: 20px; border-radius: 15px; margin: 10px 0; box-shadow: 0 5px 15px rgba(0,0,0,0.2);'>
                            """, unsafe_allow_html=True)

                            st.plotly_chart(fig, use_container_width=True)

                            # Add descriptive text below the chart
                            st.markdown("""
                            <p style='color: var(--text); text-align: center; font-style: italic; margin-top: 10px;'>
                                This chart shows the distribution of resume scores across different ranges, helping identify common performance levels.
                            </p>
                            </div>
                            """, unsafe_allow_html=True)

                        # Display recent analyses if available
                        if ai_stats["recent_analyses"]:
                            st.markdown("""
                            <h3 style='text-align: center; margin-bottom: 20px; background: linear-gradient(90deg, #4b6cb7, #182848); padding: 15px; border-radius: 10px; color: var(--text); box-shadow: 0 4px 10px rgba(0,0,0,0.2);'>
                                🕒 Recent Resume Analyses
                            </h3>
                            """, unsafe_allow_html=True)

                            # Create a more modern styled table for recent
                            # analyses
                            st.markdown("""
                            <style>
                            .modern-analyses-table {
                                width: 100%;
                                border-collapse: separate;
                                border-spacing: 0 8px;
                                margin-bottom: 20px;
                                font-family: 'Arial', sans-serif;
                            }
                            .modern-analyses-table th {
                                background: linear-gradient(135deg, #1e3c72, #2a5298);
                                color: var(--text);
                                padding: 15px;
                                text-align: left;
                                font-weight: bold;
                                font-size: 14px;
                                text-transform: uppercase;
                                letter-spacing: 1px;
                                border-radius: 8px;
                            }
                            .modern-analyses-table td {
                                padding: 15px;
                                background-color: rgba(30, 30, 30, 0.7);
                                border-top: 1px solid rgba(255, 255, 255, 0.05);
                                border-bottom: 1px solid rgba(0, 0, 0, 0.2);
                                color: var(--text);
                            }
                            .modern-analyses-table tr td:first-child {
                                border-top-left-radius: 8px;
                                border-bottom-left-radius: 8px;
                            }
                            .modern-analyses-table tr td:last-child {
                                border-top-right-radius: 8px;
                                border-bottom-right-radius: 8px;
                            }
                            .modern-analyses-table tr:hover td {
                                background-color: rgba(60, 60, 60, 0.7);
                                transform: translateY(-2px);
                                transition: all 0.2s ease;
                                box-shadow: 0 5px 15px rgba(0, 0, 0, 0.1);
                            }
                            .model-badge {
                                display: inline-block;
                                padding: 6px 12px;
                                border-radius: 20px;
                                font-weight: bold;
                                text-align: center;
                                font-size: 12px;
                                letter-spacing: 0.5px;
                                box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
                            }
                            .model-gemini {
                                background: linear-gradient(135deg, #4e54c8, #8f94fb);
                                color: var(--text-contrast);
                            }
                            .model-claude {
                                background: linear-gradient(135deg, #834d9b, #d04ed6);
                                color: var(--text-contrast);
                            }
                            .score-pill {
                                display: inline-block;
                                padding: 8px 15px;
                                border-radius: 20px;
                                font-weight: bold;
                                text-align: center;
                                min-width: 70px;
                                box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
                                color: var(--text-contrast);
                            }
                            .score-high {
                                background: linear-gradient(135deg, #11998e, #38ef7d);
                            }
                            .score-medium {
                                background: linear-gradient(135deg, #f2994a, #f2c94c);
                            }
                            .score-low {
                                background: linear-gradient(135deg, #cb2d3e, #ef473a);
                            }
                            .date-badge {
                                display: inline-block;
                                padding: 6px 12px;
                                border-radius: 20px;
                                background-color: rgba(255, 255, 255, 0.1);
                                color: var(--muted);
                                font-size: 12px;
                            }
                            .role-badge {
                                display: inline-block;
                                padding: 6px 12px;
                                border-radius: 8px;
                                background-color: rgba(33, 150, 243, 0.2);
                                color: var(--text);
                                font-size: 13px;
                                max-width: 200px;
                                white-space: nowrap;
                                overflow: hidden;
                                text-overflow: ellipsis;
                            }
                            </style>

                            <div style='background: linear-gradient(135deg, #1e3c72, #2a5298); padding: 20px; border-radius: 15px; margin: 10px 0; box-shadow: 0 5px 15px rgba(0,0,0,0.2);'>
                            <table class="modern-analyses-table">
                                <tr>
                                    <th>AI Model</th>
                                    <th>Score</th>
                                    <th>Job Role</th>
                                    <th>Date</th>
                                </tr>
                            """, unsafe_allow_html=True)

                            for analysis in ai_stats["recent_analyses"]:
                                score = analysis["score"]
                                score_class = "score-high" if score >= 80 else "score-medium" if score >= 60 else "score-low"

                                # Determine model class
                                model_name = analysis["model"]
                                model_class = "model-gemini" if "Gemini" in model_name else "model-claude" if "Claude" in model_name else ""

                                # Format the date
                                try:
                                    from datetime import datetime
                                    date_obj = datetime.strptime(
                                        analysis["date"], "%Y-%m-%d %H:%M:%S")
                                    formatted_date = date_obj.strftime(
                                        "%b %d, %Y")
                                except:
                                    formatted_date = analysis["date"]

                                st.markdown(f"""
                                <tr>
                                    <td><div class="model-badge {model_class}">{model_name}</div></td>
                                    <td><div class="score-pill {score_class}">{score}/100</div></td>
                                    <td><div class="role-badge">{analysis["job_role"]}</div></td>
                                    <td><div class="date-badge">{formatted_date}</div></td>
                                </tr>
                                """, unsafe_allow_html=True)

                            st.markdown("""
                            </table>

                            <p style='color: var(--text-contrast); text-align: center; font-style: italic; margin-top: 15px;'>
                                These are the most recent resume analyses performed by our AI models.
                            </p>
                            </div>
                            """, unsafe_allow_html=True)
                    else:
                        st.info(
                            "No AI analysis data available yet. Upload and analyze resumes to see statistics here.")
                except Exception as e:
                    st.error(f"Error loading AI analysis statistics: {str(e)}")

            # Job Role Selection for AI Analysis
            categories = list(self.job_roles.keys())
            selected_category = st.selectbox(
    "Job Category", categories, key="ai_category")

            roles = list(self.job_roles[selected_category].keys())
            selected_role = st.selectbox("Specific Role", roles, key="ai_role")

            role_info = self.job_roles[selected_category][selected_role]

            # Display role information
            st.markdown(f"""
            <div style='background-color: var(--card-bg); border: 1px solid var(--card-border); padding: 20px; border-radius: 10px; margin: 10px 0; color: var(--text);'>
                <h3 style='color: var(--text);'>{selected_role}</h3>
                <p style='color: var(--text);'>{role_info['description']}</p>
                <h4 style='color: var(--text);'>Required Skills:</h4>
                <p style='color: var(--text);'>{', '.join(role_info['required_skills'])}</p>
            </div>
            """, unsafe_allow_html=True)

            # File Upload for AI Analysis
            uploaded_file = st.file_uploader(
    "Upload your resume", type=[
        'pdf', 'docx'], key="ai_file")

            if not uploaded_file:
            # Display empty state with a prominent upload button
                st.markdown(
                self.render_empty_state(
            "fas fa-robot",
                        "Upload your resume to get AI-powered analysis and recommendations"
        ),
        unsafe_allow_html=True
    )
            else:
                # Add a prominent analyze button
                analyze_ai = st.button("🤖 Analyze with AI",
                                type="primary",
                                use_container_width=True,
                                key="analyze_ai_button")

                if analyze_ai:
                    with st.spinner(f"Analyzing your resume with {ai_model}..."):
                        # Get file content
                        text = ""
                        try:
                            if uploaded_file.type == "application/pdf":
                                text = self.analyzer.extract_text_from_pdf(
                                    uploaded_file)
                            elif uploaded_file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
                                text = self.analyzer.extract_text_from_docx(
                                    uploaded_file)
                            else:
                                text = uploaded_file.getvalue().decode()
                        except Exception as e:
                            st.error(f"Error reading file: {str(e)}")
                            st.stop()

                        # Analyze with AI
                        try:
                            # Show a loading animation
                            with st.spinner("🧠 AI is analyzing your resume..."):
                                progress_bar = st.progress(0)
                                
                                # Get the selected model
                                selected_model = "Google Gemini"
                                
                                # Update progress
                                progress_bar.progress(10)
                                
                                # Extract text from the resume
                                analyzer = AIResumeAnalyzer()
                                if uploaded_file.type == "application/pdf":
                                    resume_text = analyzer.extract_text_from_pdf(
                                        uploaded_file)
                                elif uploaded_file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
                                    resume_text = analyzer.extract_text_from_docx(
                                        uploaded_file)
                                else:
                                    # For text files or other formats
                                    resume_text = uploaded_file.getvalue().decode('utf-8')
                                
                                # Initialize the AI analyzer (moved after text extraction)
                                progress_bar.progress(30)
                                
                                # Get the job role
                                job_role = selected_role if selected_role else "Not specified"
                                
                                # Update progress
                                progress_bar.progress(50)
                                
                                # Analyze the resume with Google Gemini
                                if use_custom_job_desc and custom_job_description:
                                    # Use custom job description for analysis
                                    analysis_result = analyzer.analyze_resume_with_gemini(
                                        resume_text, job_role=job_role, job_description=custom_job_description)
                                    # Show that custom job description was used
                                    st.session_state['used_custom_job_desc'] = True
                                else:
                                    # Use standard role-based analysis
                                    analysis_result = analyzer.analyze_resume_with_gemini(
                                        resume_text, job_role=job_role)
                                    st.session_state['used_custom_job_desc'] = False

                                
                                # Update progress
                                progress_bar.progress(80)
                                
                                # Save the analysis to the database
                                if analysis_result and "error" not in analysis_result:
                                    # Extract the resume score
                                    resume_score = analysis_result.get(
                                        "resume_score", 0)
                                    
                                    # Save to database
                                    save_ai_analysis_data(
                                        None,  # No user_id needed
                                        {
                                            "model_used": selected_model,
                                            "resume_score": resume_score,
                                            "job_role": job_role
                                        }
                                    )
                                # show snowflake effect
                                st.snow()

                                # Complete the progress
                                progress_bar.progress(100)
                                
                                # Display the analysis result
                                if analysis_result and "error" not in analysis_result:
                                    st.success("✅ Analysis complete!")
                                    
                                    # Extract data from the analysis
                                    full_response = analysis_result.get(
                                        "analysis", "")
                                    resume_score = analysis_result.get(
                                        "resume_score", 0)
                                    ats_score = analysis_result.get(
                                        "ats_score", 0)
                                    model_used = analysis_result.get(
                                        "model_used", selected_model)
                                    
                                    # Store the full response in session state for download
                                    st.session_state['full_analysis'] = full_response
                                    
                                    # Display the analysis in a nice format
                                    st.markdown("## Full Analysis Report")
                                    
                                    # Get current date
                                    from datetime import datetime
                                    current_date = datetime.now().strftime("%B %d, %Y")
                                    
                                    # Create a modern styled header for the report
                                    st.markdown(f"""
                                    <div style="background-color: var(--card-bg); border: 1px solid var(--card-border); padding: 20px; border-radius: 10px; margin-bottom: 20px; color: var(--text);">
                                        <h2 style="color: var(--text); margin-bottom: 10px;">AI Resume Analysis Report</h2>
                                        <div style="display: flex; flex-wrap: wrap; gap: 20px;">
                                            <div style="flex: 1; min-width: 200px;">
                                                <p style="color: var(--text);"><strong>Job Role:</strong> {job_role if job_role else "Not specified"}</p>
                                                <p style="color: var(--text);"><strong>Analysis Date:</strong> {current_date}</p>                                                                                                                                        </div>
                                            <div style="flex: 1; min-width: 200px;">
                                                <p style="color: var(--text);"><strong>AI Model:</strong> {model_used}</p>
                                                <p style="color: var(--text);"><strong>Overall Score:</strong> {resume_score}/100 - {"Excellent" if resume_score >= 80 else "Good" if resume_score >= 60 else "Needs Improvement"}</p>
                                                {f'<p style="color: var(--accent);"><strong>✓ Custom Job Description Used</strong></p>' if st.session_state.get('used_custom_job_desc', False) else ''}
                                    </div>
                                    """, unsafe_allow_html=True)
                                    
                                    # Add gauge charts for scores
                                    import plotly.graph_objects as go
                                    
                                    col1, col2 = st.columns(2)
                                    
                                    with col1:
                                        # Resume Score Gauge
                                        fig1 = go.Figure(go.Indicator(
                                            mode="gauge+number",
                                            value=resume_score,
                                            domain={'x': [0, 1], 'y': [0, 1]},
                                            title={'text': "Resume Score", 'font': {'size': 16}},
                                            gauge={
                                                'axis': {'range': [0, 100], 'tickwidth': 1},
                                                'bar': {'color': "#4CAF50" if resume_score >= 80 else "#FFA500" if resume_score >= 60 else "#FF4444"},
                                                'bgcolor': "white",
                                                'borderwidth': 2,
                                                'bordercolor': "gray",
                                                'steps': [
                                                    {'range': [0, 40], 'color': 'rgba(255, 68, 68, 0.2)'},
                                                    {'range': [40, 60], 'color': 'rgba(255, 165, 0, 0.2)'},
                                                    {'range': [60, 80], 'color': 'rgba(255, 214, 0, 0.2)'},
                                                    {'range': [80, 100], 'color': 'rgba(76, 175, 80, 0.2)'}
                                                ],
                                                'threshold': {
                                                    'line': {'color': "red", 'width': 4},
                                                    'thickness': 0.75,
                                                    'value': 60
                                                }
                                            }
                                        ))
                                        
                                        fig1.update_layout(
                                            height=250,
                                            margin=dict(l=20, r=20, t=50, b=20),
                                        )
                                        
                                        st.plotly_chart(fig1, use_container_width=True)
                                        
                                        status = "Excellent" if resume_score >= 80 else "Good" if resume_score >= 60 else "Needs Improvement"
                                        st.markdown(f"<div style='text-align: center; font-weight: bold;'>{status}</div>", unsafe_allow_html=True)
                                    
                                    with col2:
                                        # ATS Score Gauge
                                        fig2 = go.Figure(go.Indicator(
                                            mode="gauge+number",
                                            value=ats_score,
                                            domain={'x': [0, 1], 'y': [0, 1]},
                                            title={'text': "ATS Optimization Score", 'font': {'size': 16}},
                                            gauge={
                                                'axis': {'range': [0, 100], 'tickwidth': 1},
                                                'bar': {'color': "#4CAF50" if ats_score >= 80 else "#FFA500" if ats_score >= 60 else "#FF4444"},
                                                'bgcolor': "white",
                                                'borderwidth': 2,
                                                'bordercolor': "gray",
                                                'steps': [
                                                    {'range': [0, 40], 'color': 'rgba(255, 68, 68, 0.2)'},
                                                    {'range': [40, 60], 'color': 'rgba(255, 165, 0, 0.2)'},
                                                    {'range': [60, 80], 'color': 'rgba(255, 214, 0, 0.2)'},
                                                    {'range': [80, 100], 'color': 'rgba(76, 175, 80, 0.2)'}
                                                ],
                                                'threshold': {
                                                    'line': {'color': "red", 'width': 4},
                                                    'thickness': 0.75,
                                                    'value': 60
                                                }
                                            }
                                        ))
                                        
                                        fig2.update_layout(
                                            height=250,
                                            margin=dict(l=20, r=20, t=50, b=20),
                                        )
                                        
                                        st.plotly_chart(fig2, use_container_width=True)
                                        
                                        status = "Excellent" if ats_score >= 80 else "Good" if ats_score >= 60 else "Needs Improvement"
                                        st.markdown(f"<div style='text-align: center; font-weight: bold;'>{status}</div>", unsafe_allow_html=True)

                                    # Add Job Description Match Score if custom job description was used
                                    if st.session_state.get('used_custom_job_desc', False) and custom_job_description:
                                        # Extract job match score from analysis result or calculate it
                                        job_match_score = analysis_result.get("job_match_score", 0)
                                        if not job_match_score and "job_match" in analysis_result:
                                            job_match_score = analysis_result["job_match"].get("score", 0)
                                        
                                        # If we have a job match score, display it
                                        if job_match_score:
                                            st.markdown("""
                                            <h3 style="background: linear-gradient(90deg, #4d7c0f, #84cc16); color: var(--text-contrast); padding: 10px; border-radius: 5px; margin-top: 20px;">
                                                <i class="fas fa-handshake"></i> Job Description Match Analysis
                                            </h3>
                                            """, unsafe_allow_html=True)
                                            
                                            col1, col2 = st.columns(2)
                                            
                                            with col1:
                                                # Job Match Score Gauge
                                                fig3 = go.Figure(go.Indicator(
                                                    mode="gauge+number",
                                                    value=job_match_score,
                                                    domain={'x': [0, 1], 'y': [0, 1]},
                                                    title={'text': "Job Match Score", 'font': {'size': 16}},
                                                    gauge={
                                                        'axis': {'range': [0, 100], 'tickwidth': 1},
                                                        'bar': {'color': "#4CAF50" if job_match_score >= 80 else "#FFA500" if job_match_score >= 60 else "#FF4444"},
                                                        'bgcolor': "white",
                                                        'borderwidth': 2,
                                                        'bordercolor': "gray",
                                                        'steps': [
                                                            {'range': [0, 40], 'color': 'rgba(255, 68, 68, 0.2)'},
                                                            {'range': [40, 60], 'color': 'rgba(255, 165, 0, 0.2)'},
                                                            {'range': [60, 80], 'color': 'rgba(255, 214, 0, 0.2)'},
                                                            {'range': [80, 100], 'color': 'rgba(76, 175, 80, 0.2)'}
                                                        ],
                                                        'threshold': {
                                                            'line': {'color': "red", 'width': 4},
                                                            'thickness': 0.75,
                                                            'value': 60
                                                        }
                                                    }
                                                ))
                                                
                                                fig3.update_layout(
                                                    height=250,
                                                    margin=dict(l=20, r=20, t=50, b=20),
                                                )
                                                
                                                st.plotly_chart(fig3, use_container_width=True)
                                                
                                                match_status = "Excellent Match" if job_match_score >= 80 else "Good Match" if job_match_score >= 60 else "Low Match"
                                                st.markdown(f"<div style='text-align: center; font-weight: bold;'>{match_status}</div>", unsafe_allow_html=True)
                                            
                                            with col2:
                                                st.markdown("""
                                                <div style="background-color: var(--card-bg); border: 1px solid var(--card-border); padding: 20px; border-radius: 10px; height: 100%; color: var(--text);">
                                                    <h4 style="color: var(--text); margin-bottom: 15px;">What This Means</h4>
                                                    <p style="color: var(--text);">This score represents how well your resume matches the specific job description you provided.</p>
                                                    <ul style="color: var(--text); padding-left: 20px;">
                                                        <li><strong>80-100:</strong> Excellent match - your resume is highly aligned with this job</li>
                                                        <li><strong>60-79:</strong> Good match - your resume matches many requirements</li>
                                                        <li><strong>Below 60:</strong> Consider tailoring your resume more specifically to this job</li>
                                                    </ul>
                                                </div>
                                                """, unsafe_allow_html=True)
                                    

                                    # Format the full response with better styling
                                    formatted_analysis = full_response
                                    
                                    # Replace section headers with styled headers
                                    section_styles = {
                                        "## Overall Assessment": """<div class="report-section">
                                            <h3 style="background: linear-gradient(90deg, #1e3a8a, #3b82f6); color: var(--text-contrast); padding: 10px; border-radius: 5px;">
                                                <i class="fas fa-chart-line"></i> Overall Assessment
                                            </h3>
                                            <div class="section-content">""",
                                            
                                        "## Professional Profile Analysis": """<div class="report-section">
                                            <h3 style="background: linear-gradient(90deg, #047857, #10b981); color: var(--text-contrast); padding: 10px; border-radius: 5px;">
                                                <i class="fas fa-user-tie"></i> Professional Profile Analysis
                                            </h3>
                                            <div class="section-content">""",
                                            
                                        "## Skills Analysis": """<div class="report-section">
                                            <h3 style="background: linear-gradient(90deg, #4f46e5, #818cf8); color: var(--text-contrast); padding: 10px; border-radius: 5px;">
                                                <i class="fas fa-tools"></i> Skills Analysis
                                            </h3>
                                            <div class="section-content">""",
                                            
                                        "## Experience Analysis": """<div class="report-section">
                                            <h3 style="background: linear-gradient(90deg, #9f1239, #e11d48); color: var(--text-contrast); padding: 10px; border-radius: 5px;">
                                                <i class="fas fa-briefcase"></i> Experience Analysis
                                            </h3>
                                            <div class="section-content">""",
                                            
                                        "## Education Analysis": """<div class="report-section">
                                            <h3 style="background: linear-gradient(90deg, #854d0e, #eab308); color: var(--text-contrast); padding: 10px; border-radius: 5px;">
                                                <i class="fas fa-graduation-cap"></i> Education Analysis
                                            </h3>
                                            <div class="section-content">""",
                                            
                                        "## Key Strengths": """<div class="report-section">
                                            <h3 style="background: linear-gradient(90deg, #166534, #22c55e); color: var(--text-contrast); padding: 10px; border-radius: 5px;">
                                                <i class="fas fa-check-circle"></i> Key Strengths
                                            </h3>
                                            <div class="section-content">""",
                                            
                                        "## Areas for Improvement": """<div class="report-section">
                                            <h3 style="background: linear-gradient(90deg, #9f1239, #fb7185); color: var(--text-contrast); padding: 10px; border-radius: 5px;">
                                                <i class="fas fa-exclamation-circle"></i> Areas for Improvement
                                            </h3>
                                            <div class="section-content">""",
                                            
                                        "## ATS Optimization Assessment": """<div class="report-section">
                                            <h3 style="background: linear-gradient(90deg, #0e7490, #06b6d4); color: var(--text-contrast); padding: 10px; border-radius: 5px;">
                                                <i class="fas fa-robot"></i> ATS Optimization Assessment
                                            </h3>
                                            <div class="section-content">""",
                                            
                                        "## Recommended Courses": """<div class="report-section">
                                            <h3 style="background: linear-gradient(90deg, #5b21b6, #8b5cf6); color: var(--text-contrast); padding: 10px; border-radius: 5px;">
                                                <i class="fas fa-book"></i> Recommended Courses
                                            </h3>
                                            <div class="section-content">""",
                                            
                                        "## Resume Score": """<div class="report-section">
                                            <h3 style="background: linear-gradient(90deg, #0369a1, #0ea5e9); color: var(--text-contrast); padding: 10px; border-radius: 5px;">
                                                <i class="fas fa-star"></i> Resume Score
                                            </h3>
                                            <div class="section-content">""",
                                            
                                        "## Role Alignment Analysis": """<div class="report-section">
                                            <h3 style="background: linear-gradient(90deg, #7c2d12, #ea580c); color: var(--text-contrast); padding: 10px; border-radius: 5px;">
                                                <i class="fas fa-bullseye"></i> Role Alignment Analysis
                                            </h3>
                                            <div class="section-content">""",
                                            
                                        "## Job Match Analysis": """<div class="report-section">
                                            <h3 style="background: linear-gradient(90deg, #4d7c0f, #84cc16); color: var(--text-contrast); padding: 10px; border-radius: 5px;">
                                                <i class="fas fa-handshake"></i> Job Match Analysis
                                            </h3>
                                            <div class="section-content">""",
                                    }
                                    
                                    # Apply the styling to each section
                                    for section, style in section_styles.items():
                                        if section in formatted_analysis:
                                            formatted_analysis = formatted_analysis.replace(
                                                section, style)
                                            # Add closing div tags
                                            next_section = False
                                            for next_sec in section_styles.keys():
                                                if next_sec != section and next_sec in formatted_analysis.split(style)[1]:
                                                    split_text = formatted_analysis.split(style)[1].split(next_sec)
                                                    formatted_analysis = formatted_analysis.split(style)[0] + style + split_text[0] + "</div></div>" + next_sec + "".join(split_text[1:])
                                                    next_section = True
                                                    break
                                            if not next_section:
                                                formatted_analysis = formatted_analysis + "</div></div>"
                                    
                                    # Remove any extra closing div tags that might have been added
                                    formatted_analysis = formatted_analysis.replace("</div></div></div></div>", "</div></div>")
                                    
                                    # Ensure we don't have any orphaned closing tags at the end
                                    if formatted_analysis.endswith("</div>"):
                                        # Count opening and closing div tags
                                        open_tags = formatted_analysis.count("<div")
                                        close_tags = formatted_analysis.count("</div>")
                                        
                                        # If we have more closing than opening tags, remove the extras
                                        if close_tags > open_tags:
                                            excess = close_tags - open_tags
                                            formatted_analysis = formatted_analysis[:-6 * excess]
                                    
                                    # Clean up any visible HTML tags that might appear in the text
                                    formatted_analysis = formatted_analysis.replace("&lt;/div&gt;", "")
                                    formatted_analysis = formatted_analysis.replace("&lt;div&gt;", "")
                                    formatted_analysis = formatted_analysis.replace("<div>", "<div>")  # Ensure proper opening
                                    formatted_analysis = formatted_analysis.replace("</div>", "</div>")  # Ensure proper closing
                                    
                                    # Add CSS for the report
                                    st.markdown("""
                                    <style>
                                        .report-section {
                                            margin-bottom: 25px;
                                            border: 1px solid var(--card-border);
                                            border-radius: 8px;
                                            overflow: hidden;
                                        }
                                        .section-content {
                                            padding: 15px;
                                            background-color: var(--card-bg);
                                            color: var(--text);
                                        }
                                        .report-section h3 {
                                            margin-top: 0;
                                            font-weight: 600;
                                        }
                                        .report-section ul {
                                            padding-left: 20px;
                                        }
                                        .report-section p {
                                            color: var(--text);
                                            margin-bottom: 10px;
                                        }
                                        .report-section li {
                                            color: var(--text);
                                            margin-bottom: 5px;
                                        }
                                    </style>
                                    """, unsafe_allow_html=True)

                                    # Display the formatted analysis
                                    st.markdown(f"""
                                    <div style="background-color: var(--card-bg); padding: 20px; border-radius: 10px; border: 1px solid var(--card-border); color: var(--text);">
                                        {formatted_analysis}
                                    </div>
                                    """, unsafe_allow_html=True)

                                    # Create a PDF report
                                    pdf_buffer = self.ai_analyzer.generate_pdf_report(
                                        analysis_result={
                                            "score": resume_score,
                                            "ats_score": ats_score,
                                            "model_used": model_used,
                                            "full_response": full_response,
                                            "strengths": analysis_result.get("strengths", []),
                                            "weaknesses": analysis_result.get("weaknesses", []),
                                            "used_custom_job_desc": st.session_state.get('used_custom_job_desc', False),
                                            "custom_job_description": custom_job_description if st.session_state.get('used_custom_job_desc', False) else ""
                                        },
                                        candidate_name=st.session_state.get(
                                            'candidate_name', 'Candidate'),
                                        job_role=selected_role
                                    )

                                    # PDF download button
                                    if pdf_buffer:
                                        st.download_button(
                                            label="📊 Download PDF Report",
                                            data=pdf_buffer,
                                            file_name=f"resume_analysis_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
                                            mime="application/pdf",
                                            use_container_width=True,
                                            on_click=lambda: st.balloons()
                                        )
                                    else:
                                        st.error("PDF generation failed. Please try again later.")
                                else:
                                    st.error(f"Analysis failed: {analysis_result.get('error', 'Unknown error')}")
                        except Exception as ai_error:
                            st.error(f"Error during AI analysis: {str(ai_error)}")
                            import traceback as tb
                            st.code(tb.format_exc())

        st.toast("Check out these repositories: [Awesome Java](https://github.com/VALIBOYINA-MURALI-SAI/Hiresense_AI)", icon="ℹ️")


    def render_home(self):
        apply_modern_styles()
        
        # Hero Section
        hero_section(
            "Hire Sense AI",
            "Transform your career with AI-powered resume analysis and building. Get personalized insights and create professional resumes that stand out."
        )
        
        # Features Section
        st.markdown('<div class="feature-grid">', unsafe_allow_html=True)
        
        feature_card(
            "fas fa-robot",
            "AI-Powered Analysis",
            "Get instant feedback on your resume with advanced AI analysis that identifies strengths and areas for improvement."
        )
        
        feature_card(
            "fas fa-magic",
            "Smart Resume Builder",
            "Create professional resumes with our intelligent builder that suggests optimal content and formatting."
        )
        
        feature_card(
            "fas fa-chart-line",
            "Career Insights",
            "Access detailed analytics and personalized recommendations to enhance your career prospects."
        )
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.toast("Check out these repositories: [AI-Nexus(AI/ML)](https://github.com/VALIBOYINA-MURALI-SAI/Hiresense_AI)", icon="ℹ️")

        # Call-to-Action with Streamlit navigation
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            if st.button("Get Started", key="get_started_btn", 
                        help="Click to start analyzing your resume",
                        type="primary",
                        use_container_width=True):
                st.session_state.page = 'resume_analyzer'
                st.rerun()

    def render_job_search(self):
        """Render the job search page"""
        render_job_search()

        st.toast("Check out these repositories: [GeeksforGeeks-POTD](https://github.com/VALIBOYINA-MURALI-SAI/Hiresense_AI)", icon="ℹ️")


    def render_feedback_page(self):
        """Render the feedback page"""
        apply_modern_styles()
        
        # Page Header
        page_header(
            "Feedback & Suggestions",
            "Help us improve by sharing your thoughts"
        )
        
        # Initialize feedback manager
        feedback_manager = FeedbackManager()
        
        # Create tabs for form and stats
        form_tab, stats_tab = st.tabs(["Submit Feedback", "Feedback Stats"])
        
        with form_tab:
            feedback_manager.render_feedback_form()
            
        with stats_tab:
            feedback_manager.render_feedback_stats()

        st.toast("Check out these repositories: [TryHackMe Free Rooms](https://github.com/VALIBOYINA-MURALI-SAI/Hiresense_AI)", icon="ℹ️")


    def show_repo_notification(self):
        message = """
<div style="background-color: var(--card-bg); border-radius: 10px; border: 1px solid var(--card-border); padding: 10px; margin: 10px 0; color: var(--text);">
    <div style="margin-bottom: 10px;">Check out these other repositories:</div>
    <div style="margin-bottom: 5px;"><b>Hacking Resources:</b></div>
    <ul style="margin-top: 0; padding-left: 20px;">
        <li><a href="https://github.com/VALIBOYINA-MURALI-SAI/Hiresense_AI" target="_blank" style="color: var(--accent);">TryHackMe Free Rooms</a></li>
        <li><a href="https://github.com/VALIBOYINA-MURALI-SAI/Hiresense_AI" target="_blank" style="color: var(--accent);">Awesome Hacking</a></li>
    </ul>
    <div style="margin-bottom: 5px;"><b>Programming Languages:</b></div>
    <ul style="margin-top: 0; padding-left: 20px;">
        <li><a href="https://github.com/VALIBOYINA-MURALI-SAI/Hiresense_AI" target="_blank" style="color: var(--accent);">Awesome Java</a></li>
        <li><a href="https://github.com/VALIBOYINA-MURALI-SAI/Hiresense_AI" target="_blank" style="color: var(--accent);">30 Days Of Rust</a></li>
    </ul>
    <div style="margin-bottom: 5px;"><b>Data Structures & Algorithms:</b></div>
    <ul style="margin-top: 0; padding-left: 20px;">
        <li><a href="https://github.com/VALIBOYINA-MURALI-SAI/Hiresense_AI" target="_blank" style="color: var(--accent);">GeeksforGeeks POTD</a></li>
        <li><a href="https://github.com/VALIBOYINA-MURALI-SAI/Hiresense_AI" target="_blank" style="color: var(--accent);">Leetcode POTD</a></li>
    </ul>
    <div style="margin-bottom: 5px;"><b>AI/ML Projects:</b></div>
    <ul style="margin-top: 0; padding-left: 20px;">
        <li><a href="https://github.com/VALIBOYINA-MURALI-SAI/Hiresense_AI" target="_blank" style="color: var(--accent);">AI Nexus</a></li>
    </ul>
    <div style="margin-top: 10px;">If you find this project helpful, please consider ⭐ starring the repo!</div>
</div>
"""
        st.sidebar.markdown(message, unsafe_allow_html=True)

    @staticmethod
    def _query_param_first(name: str):
        v = st.query_params.get(name)
        if isinstance(v, (list, tuple)):
            return v[0] if v else None
        return v

    def _oauth_require_login(self) -> bool:
        v = os.environ.get("HIRERESUME_REQUIRE_USER_OAUTH", "").strip().lower()
        if v in ("1", "true", "yes", "on"):
            return True
        try:
            s = st.secrets.get("require_user_oauth")
            if s is None:
                return False
            return str(s).strip().lower() in ("1", "true", "yes", "on")
        except Exception:
            return False

    def _oauth_access_granted(self) -> bool:
        if st.session_state.get("oauth_user"):
            return True
        if not any_oauth_configured():
            return True
        if self._oauth_require_login():
            return False
        return bool(st.session_state.get("oauth_browsing_guest"))

    def _clear_oauth_query_params(self):
        try:
            st.query_params.clear()
        except Exception:
            for k in ("code", "state", "error", "error_description", "scope"):
                try:
                    if k in st.query_params:
                        del st.query_params[k]
                except Exception:
                    pass

    def _handle_oauth_callback(self):
        if self._query_param_first("error"):
            st.session_state["_oauth_error"] = (
                self._query_param_first("error_description")
                or self._query_param_first("error")
                or "Sign-in cancelled."
            )
            self._clear_oauth_query_params()
            st.rerun()
            return
        code = self._query_param_first("code")
        state = self._query_param_first("state")
        if not code or not state:
            return
        expected = st.session_state.get("oauth_state")
        provider = st.session_state.get("oauth_pending_provider")
        if not expected or state != expected or not provider:
            st.session_state["_oauth_error"] = "Sign-in session expired. Please try again."
            self._clear_oauth_query_params()
            st.rerun()
            return
        redirect = oauth_redirect_uri()
        if not redirect:
            st.session_state["_oauth_error"] = "Missing oauth_redirect_uri in Streamlit secrets."
            self._clear_oauth_query_params()
            st.rerun()
            return
        try:
            if provider == "google":
                cid, cs = google_client_credentials()
                tok = exchange_google_code(str(code), cid, cs, redirect)
                access = tok.get("access_token")
                if not access:
                    raise RuntimeError("No access token from Google.")
                raw = fetch_google_profile(access)
                st.session_state.oauth_user = normalize_google_user(raw)
            elif provider == "github":
                cid, cs = github_client_credentials()
                tok = exchange_github_code(str(code), cid, cs, redirect)
                access = tok.get("access_token")
                if not access:
                    raise RuntimeError("No access token from GitHub.")
                gh_user = fetch_github_user(access)
                email = fetch_github_primary_email(access)
                st.session_state.oauth_user = normalize_github_user(gh_user, email)
            else:
                raise RuntimeError("Unknown OAuth provider.")
            st.session_state.oauth_state = None
            st.session_state.oauth_pending_provider = None
            st.session_state.oauth_login_step_google = False
            st.session_state.oauth_login_step_github = False
            st.session_state["_oauth_error"] = None
        except Exception as e:
            st.session_state["_oauth_error"] = str(e)
        self._clear_oauth_query_params()
        st.rerun()

    def _load_brand_logo_b64(self):
        """Brand logo for login / sidebar: same files as `assets/logo.jpg` with `Logo.jpeg` fallback."""
        root = os.path.dirname(__file__)
        for fname in ("logo.jpg", "Logo.jpeg"):
            path = os.path.join(root, "assets", fname)
            try:
                with open(path, "rb") as f:
                    return base64.b64encode(f.read()).decode("utf-8")
            except Exception:
                continue
        return None

    def render_oauth_login_page(self):
        st.session_state["_hire_ui_oauth_login"] = True
        self.apply_global_styles()
        err = st.session_state.pop("_oauth_error", None)
        logo_b64 = self._load_brand_logo_b64()

        _, outer_l, outer_r, _ = st.columns([0.08, 1.1, 0.95, 0.08])
        intro_col, signin_col = outer_l, outer_r

        with intro_col:
            if logo_b64:
                st.markdown(
                    f"""
                    <div style="text-align:center;margin:0 0 1rem 0;">
                        <img src="data:image/jpeg;base64,{logo_b64}" alt="Hire Sense AI"
                             style="width:112px;height:112px;object-fit:cover;border-radius:24px;
                             box-shadow:0 8px 24px rgba(0,0,0,0.1);border:2px solid rgba(26,26,26,0.1);"/>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            st.markdown("## Hire Sense AI")
            st.markdown(
                "Transform your job search with **AI-powered resume analysis and building**. "
                "Get clear feedback on ATS fit, keywords, and structure—then turn it into a polished resume."
            )
            st.markdown("**Overview**")
            st.markdown(
                """
                - **Resume analyzer** — ATS-style scores, skill gaps, and concrete improvement tips  
                - **Resume builder** — step-by-step sections and exportable documents  
                - **Dashboard** — see your analyses and activity in one place  
                - **Job search** — explore roles and align your profile  
                - **Feedback** — tell us what works so we can keep improving  
                """
            )
            st.caption(
                "Sign in with Google or GitHub when configured, or continue as a guest if your host allows it."
            )

        with signin_col:
            st.markdown("### Sign in")
            st.markdown("Use **Google** or **GitHub**, or continue without an account when available.")
            if err:
                st.error(err)
            redirect = oauth_redirect_uri()
            if any_oauth_configured() and not redirect:
                st.warning(
                    "Add **oauth_redirect_uri** to Streamlit secrets (must match the URL registered "
                    "at Google/GitHub), for example `http://localhost:8501/` for local runs."
                )

            if google_oauth_configured():
                if st.button("Continue with Google", use_container_width=True, key="oauth_btn_google"):
                    st.session_state.oauth_state = new_oauth_state()
                    st.session_state.oauth_pending_provider = "google"
                    st.session_state.oauth_login_step_google = True
                    st.session_state.oauth_login_step_github = False
                    st.rerun()
                if (
                    redirect
                    and st.session_state.get("oauth_login_step_google")
                    and st.session_state.get("oauth_pending_provider") == "google"
                ):
                    cid, _ = google_client_credentials()
                    url = build_google_authorize_url(cid, redirect, st.session_state.oauth_state)
                    st.link_button("Open Google sign-in →", url=url, use_container_width=True)

            if github_oauth_configured():
                if st.button("Continue with GitHub", use_container_width=True, key="oauth_btn_github"):
                    st.session_state.oauth_state = new_oauth_state()
                    st.session_state.oauth_pending_provider = "github"
                    st.session_state.oauth_login_step_github = True
                    st.session_state.oauth_login_step_google = False
                    st.rerun()
                if (
                    redirect
                    and st.session_state.get("oauth_login_step_github")
                    and st.session_state.get("oauth_pending_provider") == "github"
                ):
                    cid, _ = github_client_credentials()
                    url = build_github_authorize_url(cid, redirect, st.session_state.oauth_state)
                    st.link_button("Open GitHub sign-in →", url=url, use_container_width=True)

            if not google_oauth_configured() and not github_oauth_configured():
                st.info(
                    "OAuth is not configured. Add client IDs and secrets to `.streamlit/secrets.toml` "
                    "(see README). Until then, everyone can use the app."
                )
                if st.button("Continue to app", use_container_width=True, key="oauth_continue_no_config"):
                    st.session_state.oauth_browsing_guest = True
                    st.rerun()
            elif not self._oauth_require_login():
                st.markdown("---")
                if st.button("Continue without signing in", use_container_width=True, key="oauth_guest"):
                    st.session_state.oauth_browsing_guest = True
                    st.session_state.oauth_login_step_google = False
                    st.session_state.oauth_login_step_github = False
                    st.rerun()

        # Footer strip: project link, modern stack, contact, copyright (same login page)
        _gh = "https://github.com/VALIBOYINA-MURALI-SAI/Hiresense_AI"
        _li = "https://www.linkedin.com/in/valiboyina-murali-sai-ba5689250/"
        _mail = "valiboinamuralisai@gmail.com"
        _yr = datetime.now().year
        st.markdown(
            f"""
            <hr style="margin:2.25rem 0 1.25rem;border:none;border-top:1px solid var(--card-border);"/>
            <div style="max-width:760px;margin:0 auto 0.5rem;padding:1.35rem 1.5rem;border-radius:20px;
                        border:1px solid var(--card-border);background:var(--card-bg);color:var(--text);
                        box-shadow:0 6px 22px rgba(0,0,0,0.06);">
                <p style="text-align:center;margin:0 0 0.85rem;font-size:1rem;line-height:1.5;">
                    <a href="{_gh}" target="_blank" rel="noopener noreferrer"
                       style="color:var(--accent);font-weight:700;text-decoration:none;">Hire Sense AI</a>
                    <span style="color:var(--muted);"> — </span>
                    <span style="color:var(--muted);">modern, open-source web app</span>
                    <span style="color:var(--muted);"> · </span>
                    <a href="{_gh}" target="_blank" rel="noopener noreferrer"
                       style="color:var(--text);text-decoration:underline;text-underline-offset:3px;">GitHub</a>
                    <span style="color:var(--muted);"> · </span>
                    <a href="https://streamlit.io/" target="_blank" rel="noopener noreferrer"
                       style="color:var(--text);text-decoration:underline;text-underline-offset:3px;">Streamlit</a>
                </p>
                <p style="text-align:center;margin:0 0 0.65rem;font-size:0.92rem;color:var(--muted);line-height:1.55;">
                    <b style="color:var(--text);">Contact</b><br/>
                    <a href="mailto:{_mail}" style="color:var(--accent);text-decoration:none;">{_mail}</a>
                    <span style="color:var(--muted);"> · </span>
                    <a href="{_li}" target="_blank" rel="noopener noreferrer"
                       style="color:var(--accent);text-decoration:none;">LinkedIn — Murali Sai</a>
                </p>
                <p style="text-align:center;margin:0;font-size:0.78rem;color:var(--muted);letter-spacing:0.02em;">
                    © {_yr} Hire Sense AI. Developed by Murali Sai &amp; Omkar. All rights reserved.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        self.add_footer()

    def main(self):
        """Main application entry point"""
        self._handle_oauth_callback()
        if not self._oauth_access_granted():
            self.render_oauth_login_page()
            return

        st.session_state["_hire_ui_oauth_login"] = False

        # Theme (default to dark)
        if 'theme' not in st.session_state:
            st.session_state.theme = 'dark'
            
        # Sidebar logo (same assets as login page)
        logo_b64 = self._load_brand_logo_b64()

        if logo_b64:
            logo_html = f"""
            <div class="logo-container">
                <img src="data:image/jpeg;base64,{logo_b64}" class="logo" alt="Hire Sense AI Logo" />
            </div>
            <style>
            .logo-container {{
                display: flex;
                justify-content: center;
                align-items: center;
                height: 200px;
            }}
            .logo {{
                width: 120px;
                height: 120px;
                border-radius: 24px;
                animation: pulse 2.5s ease-in-out infinite;
                box-shadow: 0 0 15px rgba(0, 255, 255, 0.25);
            }}
            @keyframes pulse {{
                0% {{ transform: scale(1); box-shadow: 0 0 15px rgba(33,150,243,0.25); }}
                50% {{ transform: scale(1.08); box-shadow: 0 0 25px rgba(33,150,243,0.45); }}
                100% {{ transform: scale(1); box-shadow: 0 0 15px rgba(33,150,243,0.25); }}
            }}
            </style>
            """
        else:
            logo_html = "<div style='padding: 20px; text-align: center;'>Logo not found</div>"

        with st.sidebar:
            components.html(logo_html, height=220)
            st.title("Hire Sense AI")
            st.markdown("---")
            ou = st.session_state.get("oauth_user")
            if ou:
                st.caption(f"Signed in: {ou.get('name') or ou.get('email') or 'User'}")
                if st.button("Sign out", key="oauth_user_sign_out"):
                    st.session_state.oauth_user = None
                    st.session_state.oauth_browsing_guest = False
                    st.session_state.oauth_login_step_google = False
                    st.session_state.oauth_login_step_github = False
                    st.rerun()
            elif any_oauth_configured() and st.session_state.get("oauth_browsing_guest"):
                st.caption("Browsing as guest")

            # Navigation buttons (must stay inside with st.sidebar)
            for page_name in self.pages.keys():
                if st.button(page_name, use_container_width=True):
                    cleaned_name = page_name.lower().replace(" ", "_").replace("🏠", "").replace("🔍", "").replace("📝", "").replace("📊", "").replace("🎯", "").replace("💬", "").replace("ℹ️", "").strip()
                    st.session_state.page = cleaned_name
                    st.rerun()

            # Add some space before admin login
            st.markdown("<br><br>", unsafe_allow_html=True)
            st.markdown("---")

            # Admin Login/Logout section at bottom
            if st.session_state.get('is_admin', False):
                st.success(f"Logged in as: {st.session_state.get('current_admin_email')}")
                if st.button("Logout", key="logout_button"):
                    try:
                        log_admin_action(st.session_state.get('current_admin_email'), "logout")
                        st.session_state.is_admin = False
                        st.session_state.current_admin_email = None
                        st.success("Logged out successfully!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error during logout: {str(e)}")
            else:
                with st.expander("👤 Admin Login"):
                    admin_email_input = st.text_input("Email", key="admin_email_input")
                    admin_password = st.text_input("Password", type="password", key="admin_password_input")
                    if st.button("Login", key="login_button"):
                        try:
                            if verify_admin(admin_email_input, admin_password):
                                st.session_state.is_admin = True
                                st.session_state.current_admin_email = admin_email_input
                                log_admin_action(admin_email_input, "login")
                                st.success("Logged in successfully!")
                                st.rerun()
                            else:
                                st.error("Invalid credentials")
                        except Exception as e:
                            st.error(f"Error during login: {str(e)}")

        # Apply global styles (theme defaults to dark)
        self.apply_global_styles()

        # Force home page on first load
        if 'initial_load' not in st.session_state:
            st.session_state.initial_load = True
            st.session_state.page = 'home'
            st.rerun()
        
        # Get current page and render it
        current_page = st.session_state.get('page', 'home')
        
        # Create a mapping of cleaned page names to original names
        page_mapping = {name.lower().replace(" ", "_").replace("🏠", "").replace("🔍", "").replace("📝", "").replace("📊", "").replace("🎯", "").replace("💬", "").replace("ℹ️", "").strip(): name 
                       for name in self.pages.keys()}
        
        # Render the appropriate page
        if current_page in page_mapping:
            self.pages[page_mapping[current_page]]()
        else:
            # Default to home page if invalid page
            self.render_home()
    
        # Add footer to every page
        self.add_footer()

if __name__ == "__main__":
    app = ResumeApp()
    app.main()