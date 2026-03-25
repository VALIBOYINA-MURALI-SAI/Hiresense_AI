import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from config.database import get_database_connection
import io
import uuid
from plotly.subplots import make_subplots
from io import BytesIO

class DashboardManager:
    def __init__(self):
        self.conn = get_database_connection()
        # No fixed colors here – they will be set in render_dashboard based on theme

    def _get_theme_colors(self, theme):
        """Return a dictionary of colors based on the current theme."""
        if theme == 'light':
            return {
                'bg_dashboard': "#81ddff",
                'card_bg': "#000000",
                'text_primary': "#FFFFFF",
                'text_secondary': "#FFFFFF",
                'border': '#e0e0e0',
                'primary': '#2196F3',
                'secondary': '#1976D2',
                'success': '#4CAF50',
                'warning': '#FFC107',
                'danger': '#F44336',
                'info': '#00BCD4',
                'purple': '#9C27B0',
                'background': "#000000",          # for plotly paper_bgcolor
                'plot_bg': "#000000",              # for plotly plot_bgcolor
                'grid': '#e0e0e0',
                'line': '#cccccc'
            }
        else:  # dark
            return {
                'bg_dashboard': "#62F5FF",
                'card_bg': "#ffffff",
                'text_primary': "#000000",
                'text_secondary': "#000000",
                'border': '#333333',
                'primary': '#2196F3',
                'secondary': '#1976D2',
                'success': '#4CAF50',
                'warning': '#FFC107',
                'danger': '#F44336',
                'info': '#00BCD4',
                'purple': '#9C27B0',
                'background': "#FFFFFF",           # plotly paper_bgcolor
                'plot_bg': "#ffffff",               # plotly plot_bgcolor
                'grid': "#000000",
                'line': '#666666'
            }

    def _get_plotly_layout(self, colors):
        """Return a layout dictionary for Plotly charts using the given colors."""
        return {
            'paper_bgcolor': colors['background'],
            'plot_bgcolor': colors['plot_bg'],
            'font': {'color': colors['text_primary']},
            'title': {
                'font': {'color': colors['text_primary']}
            },
            'xaxis': {
                'title_font': {'color': colors['text_primary']},
                'tickfont': {'color': colors['text_secondary']},
                'gridcolor': colors['grid'],
                'linecolor': colors['border']
            },
            'yaxis': {
                'title_font': {'color': colors['text_primary']},
                'tickfont': {'color': colors['text_secondary']},
                'gridcolor': colors['grid'],
                'linecolor': colors['border']
            },
            'legend': {
                'font': {'color': colors['text_primary']}
            }
        }
        

    def apply_dashboard_style(self, colors):
        """Inject CSS using the theme colors."""
        st.markdown(f"""
            <style>
                .dashboard-title {{
                    font-size: 2.5rem;
                    font-weight: bold;
                    margin-bottom: 2rem;
                    color: {colors['text_primary']};
                    text-align: center;
                }}
                
                .metric-card {{
                    background-color: {colors['card_bg']};
                    border-radius: 15px;
                    padding: 1.5rem;
                    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
                    transition: transform 0.3s ease;
                    height: 100%;
                }}
                
                .metric-card:hover {{
                    transform: translateY(-5px);
                }}
                
                .metric-value {{
                    font-size: 2.5rem;
                    font-weight: bold;
                    color: {colors['primary']};
                    margin: 0.5rem 0;
                }}
                
                .metric-label {{
                    font-size: 1rem;
                    color: {colors['text_secondary']};
                }}
                
                .trend-up {{
                    color: {colors['success']};
                    font-size: 1.2rem;
                }}
                
                .trend-down {{
                    color: {colors['danger']};
                    font-size: 1.2rem;
                }}
                
                .chart-container {{
                    background-color: {colors['card_bg']};
                    border-radius: 15px;
                    padding: 1.5rem;
                    margin: 1rem 0;
                }}
                
                .section-title {{
                    font-size: 1.5rem;
                    color: {colors['text_primary']};
                    margin: 2rem 0 1rem 0;
                }}
                
                .stPlotlyChart {{
                    background-color: {colors['card_bg']};
                    border-radius: 15px;
                    padding: 1rem;
                }}
                
                div[data-testid="stHorizontalBlock"] > div {{
                    background-color: {colors['card_bg']};
                    border-radius: 15px;
                    padding: 1rem;
                    margin: 0.5rem;
                }}

                [data-testid="stMetricValue"] {{
                    font-size: 2rem !important;
                    color: {colors['text_primary']} !important;
                }}

                [data-testid="stMetricLabel"] {{
                    font-size: 1rem !important;
                    color: {colors['text_secondary']} !important;
                }}

                .dashboard-container {{
                    background: linear-gradient(135deg, {colors['primary']} 0%, {colors['secondary']} 100%);
                    padding: 2rem;
                    border-radius: 20px;
                    margin: -1rem -1rem 2rem -1rem;
                    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
                }}
                .dashboard-title {{
                    color: {colors['text_primary']};
                    font-size: 2.5rem;
                    margin-bottom: 0.5rem;
                    display: flex;
                    align-items: center;
                    gap: 1rem;
                }}
                .dashboard-icon {{
                    background: rgba(255,255,255,0.2);
                    padding: 0.5rem;
                    border-radius: 12px;
                }}
                .stats-grid {{
                    display: grid;
                    grid-template-columns: repeat(4, 1fr);
                    gap: 1.5rem;
                    margin-top: 2rem;
                }}
                .stat-card {{
                    background: rgba(255,255,255,0.1);
                    backdrop-filter: blur(10px);
                    padding: 1.5rem;
                    border-radius: 16px;
                    border: 1px solid rgba(255,255,255,0.2);
                    transition: all 0.3s ease;
                }}
                .stat-card:hover {{
                    transform: translateY(-5px);
                    background: rgba(255,255,255,0.15);
                }}
                .stat-value {{
                    font-size: 2.5rem;
                    font-weight: bold;
                    margin: 0;
                    color: {colors['text_primary']};
                }}
                .stat-label {{
                    font-size: 1rem;
                    color: rgba(255,255,255,0.7);
                    margin: 0.5rem 0 0 0;
                }}
                .section-title {{
                    color: {colors['text_primary']};
                    font-size: 1.5rem;
                    margin: 1rem 0 0.5rem 0;
                    padding-bottom: 0.5rem;
                    border-bottom: 2px solid {colors['primary']}40;
                }}
                .chart-container {{
                    background: {colors['card_bg']};
                    border-radius: 16px;
                    padding: 1rem;
                    margin-bottom: 1rem;
                }}
                .insights-grid {{
                    display: grid;
                    grid-template-columns: repeat(3, 1fr);
                    gap: 1.5rem;
                    margin-top: 1rem;
                }}
                .insight-card {{
                    background: {colors['card_bg']};
                    padding: 1.5rem;
                    border-radius: 16px;
                    border: 1px solid {colors['border']};
                }}
                .trend-indicator {{
                    display: inline-flex;
                    align-items: center;
                    padding: 0.25rem 0.5rem;
                    border-radius: 12px;
                    font-size: 0.875rem;
                    margin-left: 0.5rem;
                }}
                .trend-up {{
                    background: {colors['success']}33;
                    color: {colors['success']};
                }}
                .trend-down {{
                    background: {colors['danger']}33;
                    color: {colors['danger']};
                }}
                @keyframes fadeInUp {{
                    from {{
                        opacity: 0;
                        transform: translateY(20px);
                    }}
                    to {{
                        opacity: 1;
                        transform: translateY(0);
                    }}
                }}
                .animate-fade-in {{
                    animation: fadeInUp 0.5s ease-out forwards;
                }}
            </style>
        """, unsafe_allow_html=True)

    def get_resume_metrics(self):
        """Get resume-related metrics from database"""
        cursor = self.conn.cursor()
        
        # Get current date
        now = datetime.now()
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        start_of_week = now - timedelta(days=now.weekday())
        start_of_month = now.replace(day=1)
        
        # Fetch metrics for different time periods
        metrics = {}
        for period, start_date in [
            ('Today', start_of_day),
            ('This Week', start_of_week),
            ('This Month', start_of_month),
            ('All Time', datetime(2000, 1, 1))
        ]:
            cursor.execute("""
                SELECT 
                    COUNT(DISTINCT rd.id) as total_resumes,
                    ROUND(AVG(ra.ats_score), 1) as avg_ats_score,
                    ROUND(AVG(ra.keyword_match_score), 1) as avg_keyword_score,
                    COUNT(DISTINCT CASE WHEN ra.ats_score >= 70 THEN rd.id END) as high_scoring
                FROM resume_data rd
                LEFT JOIN resume_analysis ra ON rd.id = ra.resume_id
                WHERE rd.created_at >= ?
            """, (start_date.strftime('%Y-%m-%d %H:%M:%S'),))
            
            row = cursor.fetchone()
            if row:
                metrics[period] = {
                    'total': row[0] or 0,
                    'ats_score': row[1] or 0,
                    'keyword_score': row[2] or 0,
                    'high_scoring': row[3] or 0
                }
            else:
                metrics[period] = {
                    'total': 0,
                    'ats_score': 0,
                    'keyword_score': 0,
                    'high_scoring': 0
                }
        
        return metrics

    def get_skill_distribution(self):
        """Get skill distribution data"""
        cursor = self.conn.cursor()
        cursor.execute("""
            WITH RECURSIVE split(skill, rest) AS (
                SELECT '', skills || ','
                FROM resume_data
                UNION ALL
                SELECT
                    substr(rest, 0, instr(rest, ',')),
                    substr(rest, instr(rest, ',') + 1)
                FROM split
                WHERE rest <> ''
            ),
            SkillCategories AS (
                SELECT 
                    CASE 
                        WHEN LOWER(TRIM(skill, '[]" ')) LIKE '%python%' OR LOWER(TRIM(skill, '[]" ')) LIKE '%java%' OR 
                             LOWER(TRIM(skill, '[]" ')) LIKE '%javascript%' OR LOWER(TRIM(skill, '[]" ')) LIKE '%c++%' OR 
                             LOWER(TRIM(skill, '[]" ')) LIKE '%programming%' THEN 'Programming'
                        WHEN LOWER(TRIM(skill, '[]" ')) LIKE '%sql%' OR LOWER(TRIM(skill, '[]" ')) LIKE '%database%' OR 
                             LOWER(TRIM(skill, '[]" ')) LIKE '%mongodb%' THEN 'Database'
                        WHEN LOWER(TRIM(skill, '[]" ')) LIKE '%aws%' OR LOWER(TRIM(skill, '[]" ')) LIKE '%cloud%' OR 
                             LOWER(TRIM(skill, '[]" ')) LIKE '%azure%' THEN 'Cloud'
                        WHEN LOWER(TRIM(skill, '[]" ')) LIKE '%agile%' OR LOWER(TRIM(skill, '[]" ')) LIKE '%scrum%' OR 
                             LOWER(TRIM(skill, '[]" ')) LIKE '%management%' THEN 'Management'
                        ELSE 'Other'
                    END as category,
                    COUNT(*) as count
                FROM split
                WHERE skill <> ''
                GROUP BY category
            )
            SELECT category, count
            FROM SkillCategories
            ORDER BY count DESC
        """)
        
        categories, counts = [], []
        for row in cursor.fetchall():
            categories.append(row[0])
            counts.append(row[1])
            
        return categories, counts

    def get_weekly_trends(self):
        """Get weekly submission trends"""
        cursor = self.conn.cursor()
        now = datetime.now()
        dates = [(now - timedelta(days=x)).strftime('%Y-%m-%d') for x in range(6, -1, -1)]
        
        submissions = []
        for date in dates:
            cursor.execute("""
                SELECT COUNT(*) 
                FROM resume_data 
                WHERE DATE(created_at) = DATE(?)
            """, (date,))
            submissions.append(cursor.fetchone()[0])
            
        return [d[-3:] for d in dates], submissions  # Return shortened date format (e.g., 'Mon', 'Tue')

    def get_job_category_stats(self):
        """Get statistics by job category"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT 
                COALESCE(target_category, 'Other') as category,
                COUNT(*) as count,
                ROUND(AVG(CASE WHEN ra.ats_score >= 70 THEN 1 ELSE 0 END) * 100, 1) as success_rate
            FROM resume_data rd
            LEFT JOIN resume_analysis ra ON rd.id = ra.resume_id
            GROUP BY category
            ORDER BY count DESC
            LIMIT 5
        """)
        
        categories, success_rates = [], []
        for row in cursor.fetchall():
            categories.append(row[0])
            success_rates.append(row[2] or 0)
            
        return categories, success_rates

    def render_admin_panel(self):
        """Render admin panel with data management tools"""
        st.sidebar.markdown("### 👋 Welcome Admin!")
        st.sidebar.markdown("---")
        
        if st.sidebar.button("🚪 Logout"):
            st.session_state.is_admin = False
            st.rerun()
            
        st.sidebar.markdown("### 🛠️ Admin Tools")
        
        # Data Export Options
        export_format = st.sidebar.selectbox(
            "Export Format",
            ["Excel", "CSV", "JSON"],
            key="export_format"
        )
        
        if st.sidebar.button("📥 Export Data"):
            if export_format == "Excel":
                excel_data = self.export_to_excel()
                if excel_data:
                    st.sidebar.download_button(
                        "⬇️ Download Excel",
                        data=excel_data,
                        file_name=f"resume_data_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
            elif export_format == "CSV":
                csv_data = self.export_to_csv()
                if csv_data:
                    st.sidebar.download_button(
                        "⬇️ Download CSV",
                        data=csv_data,
                        file_name=f"resume_data_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                        mime="text/csv"
                    )
            else:
                json_data = self.export_to_json()
                if json_data:
                    st.sidebar.download_button(
                        "⬇️ Download JSON",
                        data=json_data,
                        file_name=f"resume_data_{datetime.now().strftime('%Y%m%d_%H%M')}.json",
                        mime="application/json"
                    )

        # Database Stats
        st.sidebar.markdown("### 📊 Database Stats")
        stats = self.get_database_stats()
        st.sidebar.markdown(f"""
            - Total Resumes: {stats['total_resumes']}
            - Today's Submissions: {stats['today_submissions']}
            - Storage Used: {stats['storage_size']}
        """)

    def get_resume_data(self):
        """Get all resume data"""
        cursor = self.conn.cursor()
        try:
            cursor.execute('''
            SELECT 
                r.id,
                r.name,
                r.email,
                r.phone,
                r.linkedin,
                r.github,
                r.portfolio,
                r.target_role,
                r.target_category,
                r.created_at,
                a.ats_score,
                a.keyword_match_score,
                a.format_score,
                a.section_score
            FROM resume_data r
            LEFT JOIN resume_analysis a ON r.id = a.resume_id
            ORDER BY r.created_at DESC
            ''')
            return cursor.fetchall()
        except Exception as e:
            print(f"Error fetching resume data: {str(e)}")
            return []

    def render_resume_data_section(self, colors):
        """Render resume data section with theme colors"""
        st.markdown("<h2 class='section-title'>Resume Submissions</h2>", unsafe_allow_html=True)
        
        resume_data = self.get_resume_data()
        if resume_data:
            # Convert to DataFrame (as before)
            columns = [
                'ID', 'Name', 'Email', 'Phone', 'LinkedIn', 'GitHub', 
                'Portfolio', 'Target Role', 'Target Category', 'Submission Date',
                'ATS Score', 'Keyword Match', 'Format Score', 'Section Score'
            ]
            df = pd.DataFrame(resume_data, columns=columns)
            
            score_columns = ['ATS Score', 'Keyword Match', 'Format Score', 'Section Score']
            for col in score_columns:
                df[col] = df[col].apply(lambda x: f"{x*100:.1f}%" if pd.notnull(x) else "N/A")
            
            # Style the container with theme colors
            st.markdown(f"""
            <style>
            .resume-data {{
                background-color: {colors['card_bg']};
                border-radius: 10px;
                padding: 1rem;
                margin-bottom: 1rem;
                color: {colors['text_primary']};
            }}
            </style>
            """, unsafe_allow_html=True)
            
            with st.container():
                st.markdown('<div class="resume-data">', unsafe_allow_html=True)
                
                # Add filters
                col1, col2 = st.columns(2)
                with col1:
                    target_role = st.selectbox(
                        "Filter by Target Role",
                        options=["All"] + list(df['Target Role'].unique()),
                        key="role_filter"
                    )
                with col2:
                    target_category = st.selectbox(
                        "Filter by Category",
                        options=["All"] + list(df['Target Category'].unique()),
                        key="category_filter"
                    )
                
                # Apply filters
                filtered_df = df.copy()
                if target_role != "All":
                    filtered_df = filtered_df[filtered_df['Target Role'] == target_role]
                if target_category != "All":
                    filtered_df = filtered_df[filtered_df['Target Category'] == target_category]
                
                # Display filtered data
                st.dataframe(
                    filtered_df,
                    width="stretch",
                    hide_index=True
                )
                
                # Add download buttons
                col1, col2 = st.columns(2)
                with col1:
                    # Download filtered data
                    excel_buffer = BytesIO()
                    filtered_df.to_excel(excel_buffer, index=False, engine='openpyxl')
                    excel_buffer.seek(0)
                    
                    st.download_button(
                        label="📥 Download Filtered Data",
                        data=excel_buffer,
                        file_name=f"resume_data_filtered_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key="download_filtered_data"
                    )
                
                with col2:
                    # Download all data
                    excel_buffer_all = BytesIO()
                    df.to_excel(excel_buffer_all, index=False, engine='openpyxl')
                    excel_buffer_all.seek(0)
                    
                    st.download_button(
                        label="📥 Download All Data",
                        data=excel_buffer_all,
                        file_name=f"resume_data_all_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key="download_all_data"
                    )
                
                st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.info("No resume submissions available")

    def render_admin_section(self, colors):
        """Render admin section with theme colors"""
        self.render_resume_data_section(colors)   # now passes colors correctly
        
        st.markdown(f"<h2 class='section-title'>Admin Activity Logs</h2>", unsafe_allow_html=True)
        
        admin_logs = self.get_admin_logs()
        if admin_logs:
            df = pd.DataFrame(admin_logs, columns=['Admin Email', 'Action', 'Timestamp'])
            
            st.markdown(f"""
            <style>
            .admin-logs {{
                background-color: {colors['card_bg']};
                border-radius: 10px;
                padding: 1rem;
                color: {colors['text_primary']};
            }}
            </style>
            """, unsafe_allow_html=True)
            
            with st.container():
                st.markdown('<div class="admin-logs">', unsafe_allow_html=True)
                st.dataframe(df, width="stretch", hide_index=True)
                # ... (download button) ...
                st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.info("No admin activity logs available")

    def export_to_excel(self):
        """Export data to Excel format"""
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
            df = pd.read_sql_query(query, self.conn)
            
            # Create Excel writer object
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                # Write main data
                df.to_excel(writer, sheet_name='Resume Data', index=False)
                
                # Get the workbook and the worksheet
                workbook = writer.book
                worksheet = writer.sheets['Resume Data']
                
                # Add formatting
                header_format = workbook.add_format({
                    'bold': True,
                    'text_wrap': True,
                    'valign': 'top',
                    'fg_color': '#D7E4BC',
                    'border': 1
                })
                
                # Write headers with formatting
                for col_num, value in enumerate(df.columns.values):
                    worksheet.write(0, col_num, value, header_format)
                    
                # Auto-adjust columns' width
                for i, col in enumerate(df.columns):
                    max_length = max(
                        df[col].astype(str).apply(len).max(),
                        len(str(col))
                    ) + 2
                    worksheet.set_column(i, i, min(max_length, 50))
            
            # Return the Excel file
            output.seek(0)
            return output.getvalue()
            
        except Exception as e:
            st.error(f"Error exporting to Excel: {str(e)}")
            return None

    def export_to_csv(self):
        """Export data to CSV format"""
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
            df = pd.read_sql_query(query, self.conn)
            return df.to_csv(index=False).encode('utf-8')
        except Exception as e:
            st.error(f"Error exporting to CSV: {str(e)}")
            return None

    def export_to_json(self):
        """Export data to JSON format"""
        query = """
            SELECT 
                rd.*, ra.*
            FROM resume_data rd
            LEFT JOIN resume_analysis ra ON rd.id = ra.resume_id
        """
        try:
            df = pd.read_sql_query(query, self.conn)
            return df.to_json(orient='records', date_format='iso')
        except Exception as e:
            st.error(f"Error exporting to JSON: {str(e)}")
            return None

    def get_database_stats(self):
        """Get database statistics"""
        cursor = self.conn.cursor()
        stats = {}
        
        # Total resumes
        cursor.execute("SELECT COUNT(*) FROM resume_data")
        stats['total_resumes'] = cursor.fetchone()[0]
        
        # Today's submissions
        cursor.execute("""
            SELECT COUNT(*) 
            FROM resume_data 
            WHERE DATE(created_at) = DATE('now')
        """)
        stats['today_submissions'] = cursor.fetchone()[0]
        
        # Database size (approximate)
        cursor.execute("PRAGMA page_count")
        page_count = cursor.fetchone()[0]
        cursor.execute("PRAGMA page_size")
        page_size = cursor.fetchone()[0]
        size_bytes = page_count * page_size
        
        if size_bytes < 1024:
            stats['storage_size'] = f"{size_bytes} bytes"
        elif size_bytes < 1024 * 1024:
            stats['storage_size'] = f"{size_bytes/1024:.1f} KB"
        else:
            stats['storage_size'] = f"{size_bytes/(1024*1024):.1f} MB"
        
        return stats

    def get_admin_logs(self):
        """Get admin logs"""
        cursor = self.conn.cursor()
        try:
            cursor.execute('''
            SELECT admin_email, action, timestamp
            FROM admin_logs
            ORDER BY timestamp DESC
            ''')
            return cursor.fetchall()
        except Exception as e:
            print(f"Error fetching admin logs: {str(e)}")
            return []

    def render_dashboard(self):
        """Main dashboard rendering function."""
        theme = st.session_state.get('theme', 'dark')
        colors = self._get_theme_colors(theme)
        
        self.apply_dashboard_style(colors)

        # Dashboard Header – now uses theme colors for timestamp
        st.markdown(f"""
            <div class="dashboard-container animate-fade-in">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div class="dashboard-title">
                        <span class="dashboard-icon">📊</span>
                        Resume Analytics Dashboard
                    </div>
                    <div style="color: {colors['text_secondary']}; font-size: 0.9rem;">
                        Last updated: {datetime.now().strftime('%B %d, %Y %I:%M %p')}
                    </div>
                </div>
        """, unsafe_allow_html=True)

        # Quick Stats – note: we now use f-string for the entire block,
        # and we've fixed .stat-label to use colors['text_secondary']
        stats = self.get_quick_stats()
        trend_indicators = self.get_trend_indicators()
        
        st.markdown(f"""
            <div class="stats-grid">
                <div class="stat-card">
                    <p class="stat-value">{stats['Total Resumes']}</p>
                    <p class="stat-label" style="color: {colors['text_secondary']};">Total Resumes</p>
                    <span class="trend-indicator {trend_indicators['resumes']['class']}">
                        {trend_indicators['resumes']['icon']} {trend_indicators['resumes']['value']}%
                    </span>
                </div>
                <div class="stat-card">
                    <p class="stat-value">{stats['Avg ATS Score']}</p>
                    <p class="stat-label" style="color: {colors['text_secondary']};">Avg ATS Score</p>
                    <span class="trend-indicator {trend_indicators['ats']['class']}">
                        {trend_indicators['ats']['icon']} {trend_indicators['ats']['value']}%
                    </span>
                </div>
                <div class="stat-card">
                    <p class="stat-value">{stats['High Performing']}</p>
                    <p class="stat-label" style="color: {colors['text_secondary']};">High Performing</p>
                    <span class="trend-indicator {trend_indicators['high_performing']['class']}">
                        {trend_indicators['high_performing']['icon']} {trend_indicators['high_performing']['value']}%
                    </span>
                </div>
                <div class="stat-card">
                    <p class="stat-value">{stats['Success Rate']}</p>
                    <p class="stat-label" style="color: {colors['text_secondary']};">Success Rate</p>
                    <span class="trend-indicator {trend_indicators['success_rate']['class']}">
                        {trend_indicators['success_rate']['icon']} {trend_indicators['success_rate']['value']}%
                    </span>
                </div>
            </div>
            </div>
        """, unsafe_allow_html=True)

        # Performance Analytics Section
        st.markdown(f'<div class="section-title">📈 Performance Analytics</div>', unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown('<div class="chart-container">', unsafe_allow_html=True)
            avg_ats = float(stats['Avg ATS Score'].rstrip('%'))
            fig = self.create_enhanced_ats_gauge(avg_ats, colors)
            st.plotly_chart(fig, width="stretch")
            st.markdown('</div>', unsafe_allow_html=True)

        with col2:
            st.markdown('<div class="chart-container">', unsafe_allow_html=True)
            fig = self.create_skill_distribution_chart(colors)
            st.plotly_chart(fig, width="stretch")
            st.markdown('</div>', unsafe_allow_html=True)

        # Additional Analytics
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown('<div class="chart-container">', unsafe_allow_html=True)
            fig = self.create_submission_trends_chart(colors)
            st.plotly_chart(fig, width="stretch")
            st.markdown('</div>', unsafe_allow_html=True)

        with col2:
            st.markdown('<div class="chart-container">', unsafe_allow_html=True)
            fig = self.create_job_category_chart(colors)
            st.plotly_chart(fig, width="stretch")
            st.markdown('</div>', unsafe_allow_html=True)

        # Key Insights Section
        st.markdown('<div class="section-title">🎯 Key Insights</div>', unsafe_allow_html=True)
        insights = self.get_detailed_insights()
        
        st.markdown('<div class="insights-grid">', unsafe_allow_html=True)
        for insight in insights:
            st.markdown(f"""
                <div class="insight-card">
                    <h3 style="color: {colors['primary']}; margin-bottom: 1rem;">
                        {insight['icon']} {insight['title']}
                    </h3>
                    <p style="color: {colors['text_secondary']}; margin: 0;">
                        {insight['description']}
                    </p>
                    <div style="margin-top: 1rem;">
                        <span class="trend-indicator {insight['trend_class']}">
                            {insight['trend_icon']} {insight['trend_value']}
                        </span>
                    </div>
                </div>
            """, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        # Admin logs section (unchanged)
        if st.session_state.get('is_admin', False):
            self.render_admin_section(colors)   # now passes colors

    def get_trend_indicators(self):
        """Get trend indicators for stats"""
        cursor = self.conn.cursor()
        indicators = {}
        
        # Compare with last week's data
        for metric in ['resumes', 'ats', 'high_performing', 'success_rate']:
            try:
                if metric == 'resumes':
                    cursor.execute("""
                        SELECT 
                            (COUNT(*) - (
                                SELECT COUNT(*) 
                                FROM resume_data 
                                WHERE created_at < date('now', '-7 days')
                            )) * 100.0 / 
                            NULLIF((
                                SELECT COUNT(*) 
                                FROM resume_data 
                                WHERE created_at < date('now', '-7 days')
                            ), 0)
                        FROM resume_data
                    """)
                elif metric == 'ats':
                    cursor.execute("""
                        SELECT 
                            (AVG(ats_score) - (
                                SELECT AVG(ats_score) 
                                FROM resume_analysis 
                                WHERE created_at < date('now', '-7 days')
                            )) * 100.0 / 
                            NULLIF((
                                SELECT AVG(ats_score) 
                                FROM resume_analysis 
                                WHERE created_at < date('now', '-7 days')
                            ), 0)
                        FROM resume_analysis
                    """)
                
                change = cursor.fetchone()[0] or 0
                indicators[metric] = {
                    'value': abs(round(change, 1)),
                    'icon': '↑' if change >= 0 else '↓',
                    'class': 'trend-up' if change >= 0 else 'trend-down'
                }
            except Exception:
                indicators[metric] = {
                    'value': 0,
                    'icon': '→',
                    'class': 'trend-neutral'
                }
        
        return indicators

    def get_detailed_insights(self):
        """Get detailed insights from the database"""
        cursor = self.conn.cursor()
        insights = []
        
        # Most Successful Job Category
        cursor.execute("""
            SELECT target_category, AVG(ats_score) as avg_score,
                   COUNT(*) as submission_count
            FROM resume_data rd
            JOIN resume_analysis ra ON rd.id = ra.resume_id
            GROUP BY target_category
            ORDER BY avg_score DESC
            LIMIT 1
        """)
        top_category = cursor.fetchone()
        if top_category:
            insights.append({
                'title': 'Top Performing Category',
                'icon': '🏆',
                'description': f"{top_category[0]} leads with {top_category[1]:.1f}% average ATS score across {top_category[2]} submissions",
                'trend_class': 'trend-up',
                'trend_icon': '↑',
                'trend_value': f"{top_category[1]:.1f}%"
            })
        
        # Recent Improvement
        cursor.execute("""
            SELECT 
                (SELECT AVG(ats_score) FROM resume_analysis 
                 WHERE created_at >= date('now', '-7 days')) as recent_score,
                (SELECT AVG(ats_score) FROM resume_analysis 
                 WHERE created_at < date('now', '-7 days')) as old_score
        """)
        scores = cursor.fetchone()
        if scores and scores[0] and scores[1]:
            change = scores[0] - scores[1]
            insights.append({
                'title': 'Weekly Trend',
                'icon': '📈',
                'description': f"ATS scores have {'improved' if change >= 0 else 'decreased'} by {abs(change):.1f}% in the last week",
                'trend_class': 'trend-up' if change >= 0 else 'trend-down',
                'trend_icon': '↑' if change >= 0 else '↓',
                'trend_value': f"{abs(change):.1f}%"
            })
        
        # Most Common Skills
        cursor.execute("""
            WITH RECURSIVE
            split(skill, rest) AS (
                SELECT '', skills || ',' 
                FROM resume_data 
                WHERE skills IS NOT NULL
                UNION ALL
                SELECT
                    substr(rest, 0, instr(rest, ',')),
                    substr(rest, instr(rest, ',') + 1)
                FROM split 
                WHERE rest <> ''
            ),
            cleaned_skills AS (
                SELECT TRIM(REPLACE(REPLACE(skill, '[', ''), ']', '')) as skill
                FROM split 
                WHERE skill <> ''
            )
            SELECT skill, COUNT(*) as count
            FROM cleaned_skills
            GROUP BY skill
            ORDER BY count DESC
            LIMIT 3
        """)
        top_skills = cursor.fetchall()
        if top_skills:
            skills_text = f"Most in-demand skills: Python ({top_skills[0][1]} resumes), Java ({top_skills[1][1]} resumes), Express ({top_skills[2][1]} resumes)"
            insights.append({
                'title': 'Top Skills',
                'icon': '💡',
                'description': f"Most in-demand skills: {skills_text}",
                'trend_class': 'trend-up',
                'trend_icon': '🔝',
                'trend_value': f"Top {len(top_skills)}"
            })
        
        return insights

    def get_quick_stats(self):
        """Get quick statistics for the dashboard"""
        cursor = self.conn.cursor()
        
        # Total Resumes
        cursor.execute("SELECT COUNT(*) FROM resume_data")
        total_resumes = cursor.fetchone()[0]
        
        # Average ATS Score
        cursor.execute("SELECT AVG(ats_score) FROM resume_analysis")
        avg_ats = cursor.fetchone()[0] or 0
        
        # High Performing Resumes
        cursor.execute("SELECT COUNT(*) FROM resume_analysis WHERE ats_score >= 70")
        high_performing = cursor.fetchone()[0]
        
        # Success Rate
        success_rate = (high_performing / total_resumes * 100) if total_resumes > 0 else 0
        
        return {
            "Total Resumes": f"{total_resumes:,}",
            "Avg ATS Score": f"{avg_ats:.1f}%",
            "High Performing": f"{high_performing:,}",
            "Success Rate": f"{success_rate:.1f}%"
        }

    def create_enhanced_ats_gauge(self, value, colors):
        """Create an enhanced ATS score gauge chart."""
        reference = 70  # Target score
        delta = value - reference
        
        fig = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=value,
            delta={
                'reference': reference,
                'valueformat': '.1f',
                'increasing': {'color': colors['success']},
                'decreasing': {'color': colors['danger']}
            },
            number={'font': {'size': 40, 'color': colors['text_primary']}},
            gauge={
                'axis': {
                    'range': [0, 100],
                    'tickwidth': 1,
                    'tickcolor': colors['text_secondary'],
                    'tickfont': {'color': colors['text_secondary']}
                },
                'bar': {'color': colors['primary']},
                'bgcolor': 'rgba(0,0,0,0)',
                'borderwidth': 2,
                'bordercolor': colors['border'],
                'steps': [
                    {'range': [0, 40], 'color': colors['danger']},
                    {'range': [40, 70], 'color': colors['warning']},
                    {'range': [70, 100], 'color': colors['success']}
                ],
                'threshold': {
                    'line': {'color': colors['text_primary'], 'width': 4},
                    'thickness': 0.75,
                    'value': reference
                }
            }
        ))
        
        layout = self._get_plotly_layout(colors)
        layout.update({
            'title': {
                'text': 'ATS Score Performance',
                'font': {'size': 24, 'color': colors['text_primary']},
                'y': 0.85
            },
            'height': 350,
            'margin': dict(l=20, r=20, t=80, b=20)
        })
        fig.update_layout(**layout)
        return fig

    def create_skill_distribution_chart(self, colors):
        """Create a skill distribution chart."""
        categories, counts = self.get_skill_distribution()
        
        fig = go.Figure(data=[
            go.Bar(
                x=categories,
                y=counts,
                marker_color=colors['info'],
                text=counts,
                textposition='auto',
            )
        ])
        
        layout = self._get_plotly_layout(colors)
        layout.update({
            'title': {
                'text': 'Skill Distribution',
                'y': 0.95,
                'x': 0.5,
                'xanchor': 'center',
                'yanchor': 'top',
                'font': {'color': colors['text_primary']}
            },
            'height': 350,
            'margin': dict(l=40, r=40, t=60, b=40),
            'xaxis': {
                **layout['xaxis'],
                'showgrid': False,
                'showline': True,
                'linecolor': colors['border']
            },
            'yaxis': {
                **layout['yaxis'],
                'showgrid': True,
                'gridcolor': colors['grid'],
                'zeroline': False
            },
            'bargap': 0.3
        })
        fig.update_layout(**layout)
        return fig

    def create_submission_trends_chart(self, colors):
        """Create a weekly submission trend chart."""
        dates, submissions = self.get_weekly_trends()
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=dates,
            y=submissions,
            mode='lines+markers',
            line=dict(color=colors['info'], width=3),
            marker=dict(size=8, color=colors['info'])
        ))
        
        layout = self._get_plotly_layout(colors)
        layout.update({
            'title': 'Weekly Submission Pattern',
            'height': 300,
            'margin': dict(l=20, r=20, t=50, b=20)
        })
        fig.update_layout(**layout)
        return fig

    def create_job_category_chart(self, colors):
        """Create a success rate by category chart."""
        categories, rates = self.get_job_category_stats()
        fig = go.Figure(go.Bar(
            x=categories,
            y=rates,
            marker_color=[colors['success'], colors['info'], 
                        colors['warning'], colors['purple'], 
                        colors['secondary']],
            text=[f"{rate}%" for rate in rates],
            textposition='auto',
        ))
        
        layout = self._get_plotly_layout(colors)
        layout.update({
            'title': 'Success Rate by Job Category',
            'height': 300,
            'margin': dict(l=20, r=20, t=50, b=20)
        })
        fig.update_layout(**layout)
        return fig