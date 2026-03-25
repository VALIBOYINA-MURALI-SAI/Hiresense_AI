import streamlit as st
import sqlite3
from datetime import datetime
import pandas as pd

class FeedbackManager:
    def __init__(self):
        self.db_path = "feedback/feedback.db"
        self.setup_database()

    def setup_database(self):
        """Create feedback table if it doesn't exist"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rating INTEGER,
                usability_score INTEGER,
                feature_satisfaction INTEGER,
                missing_features TEXT,
                improvement_suggestions TEXT,
                user_experience TEXT,
                timestamp DATETIME
            )
        ''')
        conn.commit()
        conn.close()

    def save_feedback(self, feedback_data):
        """Save feedback to database"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''
            INSERT INTO feedback (
                rating, usability_score, feature_satisfaction,
                missing_features, improvement_suggestions,
                user_experience, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            feedback_data['rating'],
            feedback_data['usability_score'],
            feedback_data['feature_satisfaction'],
            feedback_data['missing_features'],
            feedback_data['improvement_suggestions'],
            feedback_data['user_experience'],
            datetime.now()
        ))
        conn.commit()
        conn.close()

    def get_feedback_stats(self):
        """Get feedback statistics"""
        conn = sqlite3.connect(self.db_path)
        df = pd.read_sql_query("SELECT * FROM feedback", conn)
        conn.close()
        
        if df.empty:
            return {
                'avg_rating': 0,
                'avg_usability': 0,
                'avg_satisfaction': 0,
                'total_responses': 0
            }
        
        return {
            'avg_rating': df['rating'].mean(),
            'avg_usability': df['usability_score'].mean(),
            'avg_satisfaction': df['feature_satisfaction'].mean(),
            'total_responses': len(df)
        }

    def _inject_feedback_page_styles(self):
        st.markdown(
            """
            <style>
            .hire-fb-hero, .hire-fb-panel {
                max-width: 640px;
                margin-left: auto;
                margin-right: auto;
            }
            .hire-fb-hero {
                border-bottom: 1px solid var(--card-border);
                padding: 0 0 0.75rem 0;
                margin-bottom: 1rem;
            }
            .hire-fb-hero h3 {
                margin: 0;
                font-size: 1.25rem;
                font-weight: 700;
                color: var(--text);
                letter-spacing: -0.02em;
            }
            .hire-fb-panel {
                background: var(--card-bg);
                border: 1px solid var(--card-border);
                border-radius: 12px;
                padding: 0.85rem 1rem 0.95rem;
                margin-bottom: 0.65rem;
            }
            .hire-fb-panel-title {
                font-size: 0.88rem;
                font-weight: 600;
                color: var(--muted);
                text-transform: uppercase;
                letter-spacing: 0.06em;
                margin: 0 0 0.5rem 0;
            }
            .hire-fb-val-row {
                margin: 0.35rem 0 0 0;
            }
            .hire-fb-badge {
                display: inline-flex;
                align-items: center;
                justify-content: center;
                min-width: 2.1rem;
                padding: 0.2rem 0.55rem;
                border-radius: 8px;
                font-weight: 800;
                font-size: 0.95rem;
                color: #fff;
                box-shadow: 0 2px 8px rgba(0,0,0,0.12);
            }
            .hire-fb-badge.b1, .hire-fb-badge.b2 {
                background: linear-gradient(135deg, #b91c1c, #ef4444);
            }
            .hire-fb-badge.b3 {
                background: linear-gradient(135deg, #ca8a04, #facc15);
                color: #171717 !important;
            }
            .hire-fb-badge.b4, .hire-fb-badge.b5 {
                background: linear-gradient(135deg, #15803d, #22c55e);
            }
            /* Select-slider: red → yellow → green track */
            .hire-fb-rate div[data-testid="stSelectSlider"] [data-baseweb="slider"] [role="slider"] {
                background-color: #fafafa !important;
                border: 3px solid var(--card-bg) !important;
                box-shadow: 0 0 0 2px rgba(0,0,0,0.12), 0 4px 10px rgba(0,0,0,0.18) !important;
                width: 22px !important;
                height: 22px !important;
            }
            .hire-fb-rate div[data-testid="stSelectSlider"] [data-baseweb="slider"] [data-baseweb="track"] {
                border-radius: 999px !important;
                height: 12px !important;
                background: rgba(0,0,0,0.08) !important;
            }
            .hire-fb-rate div[data-testid="stSelectSlider"] [data-baseweb="slider"] [data-baseweb="track"] > div:first-child {
                border-radius: 999px !important;
                background: linear-gradient(90deg, #ef4444 0%, #eab308 50%, #22c55e 100%) !important;
            }
            /* Let full R→Y→G show (some builds add a second fill layer) */
            .hire-fb-rate div[data-testid="stSelectSlider"] [data-baseweb="slider"] [data-baseweb="track"] > div:not(:first-child) {
                background: transparent !important;
            }
            .hire-fb-rate div[data-testid="stSelectSlider"] [data-baseweb="slider"] [data-baseweb="tick"] {
                font-size: 0.8rem !important;
                font-weight: 700 !important;
                color: var(--text) !important;
            }
            .hire-fb-rate div[data-testid="stSelectSlider"] {
                padding-top: 0.1rem;
                padding-bottom: 0.05rem;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )

    def _rating_dragger(self, *, panel_title: str, key: str) -> int:
        """Discrete 1–5 rating: R→Y→G track + numeric badge (no stars)."""
        st.markdown('<div class="hire-fb-panel">', unsafe_allow_html=True)
        st.markdown(
            f'<p class="hire-fb-panel-title">{panel_title}</p>', unsafe_allow_html=True
        )
        st.markdown('<div class="hire-fb-rate">', unsafe_allow_html=True)
        value = st.select_slider(
            " ",
            options=[1, 2, 3, 4, 5],
            value=5,
            format_func=lambda n: str(n),
            key=key,
            label_visibility="collapsed",
            width="stretch",
        )
        st.markdown("</div>", unsafe_allow_html=True)
        v = int(value)
        st.markdown(
            f'<p class="hire-fb-val-row"><span class="hire-fb-badge b{v}">{v}</span></p>',
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)
        return v

    def render_feedback_form(self):
        """Modern feedback form aligned with app chrome (cards + accent)."""
        self._inject_feedback_page_styles()

        st.markdown(
            '<div class="hire-fb-hero"><h3>Feedback</h3></div>',
            unsafe_allow_html=True,
        )

        rating = self._rating_dragger(panel_title="Overall", key="fb_rating")
        usability_score = self._rating_dragger(panel_title="Ease of use", key="fb_usability")
        feature_satisfaction = self._rating_dragger(panel_title="Features", key="fb_features")

        st.markdown('<div class="hire-fb-panel">', unsafe_allow_html=True)
        st.markdown(
            '<p class="hire-fb-panel-title">Comments · optional</p>',
            unsafe_allow_html=True,
        )
        comments = st.text_area(
            "Comments",
            placeholder="Optional notes…",
            label_visibility="collapsed",
            height=88,
            key="fb_comments",
        )
        st.markdown("</div>", unsafe_allow_html=True)

        if st.button(
            "Submit feedback",
            type="primary",
            width="stretch",
            key="submit_feedback",
        ):
            try:
                with st.spinner("Saving your feedback…"):
                    feedback_data = {
                        "rating": rating,
                        "usability_score": usability_score,
                        "feature_satisfaction": feature_satisfaction,
                        "missing_features": "",
                        "improvement_suggestions": "",
                        "user_experience": comments or "",
                    }
                    self.save_feedback(feedback_data)
                st.success("Thank you — your feedback was saved. It helps us improve Hire Sense AI.")
                st.balloons()
            except Exception as e:
                st.error(f"Could not save feedback: {str(e)}")

    def render_feedback_stats(self):
        """Summary metrics + simple chart."""
        self._inject_feedback_page_styles()
        stats = self.get_feedback_stats()

        st.markdown(
            '<div class="hire-fb-hero"><h3>Stats</h3></div>',
            unsafe_allow_html=True,
        )

        if stats["total_responses"] == 0:
            st.info("No responses yet. Use **Submit Feedback** to add the first one.")
            return

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("Responses", f"{int(stats['total_responses']):,}")
        with c2:
            st.metric("Avg rating", f"{stats['avg_rating']:.2f}", help="Overall 1–5")
        with c3:
            st.metric("Ease of use", f"{stats['avg_usability']:.2f}", help="Usability 1–5")
        with c4:
            st.metric("Features", f"{stats['avg_satisfaction']:.2f}", help="Satisfaction 1–5")

        st.markdown("<br/>", unsafe_allow_html=True)
        chart_df = pd.DataFrame(
            {
                "Area": ["Overall", "Ease of use", "Features"],
                "Average (out of 5)": [
                    round(stats["avg_rating"], 2),
                    round(stats["avg_usability"], 2),
                    round(stats["avg_satisfaction"], 2),
                ],
            }
        )
        st.bar_chart(chart_df.set_index("Area"), width="stretch", height=280)