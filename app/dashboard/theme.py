import streamlit as st


def apply_rescuemesh_theme():
    st.markdown(
        """
        <style>

        /* =====================================================
           RESCUEMESH COLOR PALETTE
        ===================================================== */

        :root {
            --rm-bg: #efe3d3;
            --rm-bg-light: #f5eadc;

            --rm-card: #faf2e7;
            --rm-card-hover: #fff8ef;

            --rm-border: #d8c2a8;
            --rm-border-dark: #bea58a;

            --rm-green: #355844;
            --rm-green-dark: #203d2d;
            --rm-green-medium: #5d8064;
            --rm-green-light: #dce9d9;

            --rm-text: #20372a;
            --rm-text-secondary: #405c49;

            --rm-warning: #c78645;
            --rm-warning-bg: #f8ead8;

            --rm-danger: #a95f50;
            --rm-danger-bg: #f5dfd9;

            --rm-success-bg: #dcebd8;
        }


        /* =====================================================
           FULL PAGE BACKGROUND
        ===================================================== */

        html,
        body,
        .stApp {
            background-color: var(--rm-bg) !important;
            color: var(--rm-text) !important;
        }

        [data-testid="stAppViewContainer"] {
            background:
                linear-gradient(
                    180deg,
                    #efe3d3 0%,
                    #f2e6d7 45%,
                    #eee0ce 100%
                ) !important;
        }

        [data-testid="stHeader"] {
            background: transparent !important;
        }

        [data-testid="stToolbar"] {
            background: transparent !important;
        }


        /* =====================================================
           CENTER THE CONTENT
        ===================================================== */

        .main .block-container,
        [data-testid="stMainBlockContainer"] {
            max-width: 1120px !important;
            margin-left: auto !important;
            margin-right: auto !important;

            padding-top: 1.8rem !important;
            padding-left: 2rem !important;
            padding-right: 2rem !important;
            padding-bottom: 3rem !important;
        }


        /* =====================================================
           GLOBAL TEXT
        ===================================================== */

        html,
        body,
        p,
        span,
        label,
        li,
        div {
            color: var(--rm-text-secondary);
        }

        h1,
        h2,
        h3,
        h4,
        h5,
        h6 {
            color: var(--rm-green-dark) !important;
            font-weight: 700 !important;
            letter-spacing: -0.015em !important;
        }

        h1 {
            font-weight: 800 !important;
        }

        p {
            line-height: 1.55 !important;
        }
        
        p {
            color: var(--rm-text-secondary) !important;
            font-size: 0.98rem !important;
            line-height: 1.6 !important;
        }

        [data-testid="stCaptionContainer"],
        [data-testid="stCaptionContainer"] p {
            color: #526a58 !important;
            font-size: 0.95rem !important;
            line-height: 1.55 !important;
            font-weight: 450 !important;
        }

        label {
            color: var(--rm-green-dark) !important;
            font-weight: 500 !important;
        }


        /* =====================================================
           DIVIDERS
        ===================================================== */

        hr {
            border: none !important;
            border-top: 1px solid var(--rm-border) !important;
            margin-top: 1.4rem !important;
            margin-bottom: 1.4rem !important;
        }


        /* =====================================================
           FORMS
        ===================================================== */

        [data-testid="stForm"] {
            background: var(--rm-card) !important;

            border:
                1px solid
                var(--rm-border) !important;

            border-radius: 18px !important;

            padding:
                1.2rem 1.25rem !important;

            box-shadow:
                0 4px 14px
                rgba(
                    76,
                    60,
                    42,
                    0.07
                ) !important;
        }


        /* =====================================================
           SELECTBOX
        ===================================================== */

        [data-testid="stSelectbox"]
        div[data-baseweb="select"]
        > div {

            background:
                var(--rm-card) !important;

            border:
                1px solid
                var(--rm-green-dark) !important;

            border-radius:
                10px !important;

            color:
                var(--rm-green-dark) !important;

            box-shadow:
                none !important;
        }

        [data-testid="stSelectbox"]
        div[data-baseweb="select"]
        span {

            color:
                var(--rm-green-dark) !important;
        }

        [data-testid="stSelectbox"]
        svg {

            color:
                var(--rm-green-dark) !important;

            fill:
                var(--rm-green-dark) !important;
        }


        /* =====================================================
           TEXT INPUTS
        ===================================================== */

        [data-testid="stTextInput"]
        div[data-baseweb="input"] {

            background:
                var(--rm-card) !important;

            border:
                1px solid
                var(--rm-green-dark) !important;

            border-radius:
                10px !important;

            box-shadow:
                none !important;
        }

        [data-testid="stTextInput"]
        input {

            background:
                var(--rm-card) !important;

            color:
                var(--rm-green-dark) !important;

            -webkit-text-fill-color:
                var(--rm-green-dark) !important;

            border:
                none !important;
        }


        /* =====================================================
           NUMBER INPUT
           Matches Food Type field
        ===================================================== */

        [data-testid="stNumberInput"]
        div[data-baseweb="input"] {

            background:
                var(--rm-card) !important;

            border:
                1px solid
                var(--rm-green-dark) !important;

            border-radius:
                10px !important;

            box-shadow:
                none !important;

            overflow:
                hidden !important;
        }

        [data-testid="stNumberInput"]
        input {

            background:
                var(--rm-card) !important;

            color:
                var(--rm-green-dark) !important;

            -webkit-text-fill-color:
                var(--rm-green-dark) !important;

            border:
                none !important;

            box-shadow:
                none !important;

            font-weight:
                500 !important;
        }

        [data-testid="stNumberInput"]
        button {

            background:
                #e6d7c4 !important;

            color:
                var(--rm-green-dark) !important;

            border:
                none !important;

            border-left:
                1px solid
                var(--rm-border) !important;

            border-radius:
                0 !important;
        }

        [data-testid="stNumberInput"]
        button:hover {

            background:
                #dbc7ae !important;
        }

        [data-testid="stNumberInput"]
        button svg {

            color:
                var(--rm-green-dark) !important;

            fill:
                var(--rm-green-dark) !important;
        }


        /* =====================================================
           TIME INPUT
           Available From + Pickup Deadline
        ===================================================== */

        [data-testid="stTimeInput"] {
            color-scheme: light !important;
        }

        [data-testid="stTimeInput"]
        div[data-baseweb="input"] {

            background:
                var(--rm-card) !important;

            border:
                1px solid
                var(--rm-green-dark) !important;

            border-radius:
                10px !important;

            box-shadow:
                none !important;

            overflow:
                hidden !important;

            color-scheme:
                light !important;
        }

        [data-testid="stTimeInput"]
        div[data-baseweb="input"]
        > div {

            background:
                var(--rm-card) !important;
        }

        [data-testid="stTimeInput"]
        input {

            background:
                var(--rm-card) !important;

            background-color:
                var(--rm-card) !important;

            color:
                var(--rm-green-dark) !important;

            -webkit-text-fill-color:
                var(--rm-green-dark) !important;

            border:
                none !important;

            box-shadow:
                none !important;

            color-scheme:
                light !important;

            font-weight:
                500 !important;
        }

        input[type="time"] {

            background:
                var(--rm-card) !important;

            background-color:
                var(--rm-card) !important;

            color:
                var(--rm-green-dark) !important;

            -webkit-text-fill-color:
                var(--rm-green-dark) !important;

            color-scheme:
                light !important;
        }

        input[type="time"]::-webkit-datetime-edit,
        input[type="time"]::-webkit-datetime-edit-fields-wrapper,
        input[type="time"]::-webkit-datetime-edit-hour-field,
        input[type="time"]::-webkit-datetime-edit-minute-field,
        input[type="time"]::-webkit-datetime-edit-text {

            background:
                transparent !important;

            color:
                var(--rm-green-dark) !important;

            -webkit-text-fill-color:
                var(--rm-green-dark) !important;
        }

        input[type="time"]
        ::-webkit-calendar-picker-indicator {

            filter:
                none !important;

            opacity:
                0.7 !important;
        }


        /* =====================================================
           INPUT FOCUS
        ===================================================== */

        [data-testid="stNumberInput"]
        div[data-baseweb="input"]:focus-within,

        [data-testid="stTimeInput"]
        div[data-baseweb="input"]:focus-within,

        [data-testid="stTextInput"]
        div[data-baseweb="input"]:focus-within {

            border-color:
                var(--rm-green-medium) !important;

            box-shadow:
                0 0 0 1px
                var(--rm-green-medium) !important;
        }


        /* =====================================================
           REMOVE "PRESS ENTER TO SUBMIT"
        ===================================================== */

        [data-testid="InputInstructions"] {
            display: none !important;
        }


        /* =====================================================
           BUTTONS
        ===================================================== */

        .stButton > button,
        [data-testid="baseButton-primary"],
        [data-testid="baseButton-secondary"],
        .stFormSubmitButton > button {

            background:
                var(--rm-green-medium) !important;

            color:
                white !important;

            border:
                none !important;

            border-radius:
                11px !important;

            font-weight:
                600 !important;

            min-height:
                42px !important;

            box-shadow:
                0 3px 8px
                rgba(
                    50,
                    80,
                    55,
                    0.13
                ) !important;

            transition:
                all 0.18s ease !important;
        }

        .stButton > button *,
        [data-testid="baseButton-primary"] *,
        [data-testid="baseButton-secondary"] *,
        .stFormSubmitButton > button * {

            color:
                white !important;
        }

        .stButton > button:hover,
        [data-testid="baseButton-primary"]:hover,
        [data-testid="baseButton-secondary"]:hover,
        .stFormSubmitButton > button:hover {

            background:
                var(--rm-green-dark) !important;

            color:
                white !important;

            transform:
                translateY(-1px);
        }


        /* =====================================================
           METRIC CARDS
        ===================================================== */

        div[data-testid="metric-container"],
        [data-testid="stMetric"] {

            background:
                var(--rm-card) !important;

            border:
                1px solid
                var(--rm-border) !important;

            padding:
                1.1rem 1.2rem !important;

            border-radius:
                17px !important;

            box-shadow:
                0 3px 10px
                rgba(
                    75,
                    60,
                    45,
                    0.055
                ) !important;
        }

        [data-testid="stMetricLabel"],
        [data-testid="stMetricLabel"] p {

            color:
                var(--rm-green) !important;

            font-weight:
                500 !important;
        }

        [data-testid="stMetricValue"],
        [data-testid="stMetricValue"] div {

            color:
                var(--rm-green-dark) !important;

            font-weight:
                750 !important;
        }


        /* =====================================================
           STATUS / ALERT BOXES
        ===================================================== */

        [data-testid="stAlert"] {

            border-radius:
                13px !important;

            border:
                1px solid
                #b7ceb3 !important;

            box-shadow:
                none !important;
        }

        [data-testid="stAlert"]
        p {

            color:
                var(--rm-green-dark) !important;
        }

        div[data-baseweb="notification"] {

            color:
                var(--rm-green-dark) !important;
        }


        /* =====================================================
           NAVIGATION RADIO PILLS
        ===================================================== */

        div[role="radiogroup"] {

            gap:
                0.4rem !important;

            background:
                transparent !important;
        }

        div[role="radiogroup"]
        label {

            background:
                var(--rm-card) !important;

            border:
                1px solid
                var(--rm-border) !important;

            border-radius:
                999px !important;

            padding:
                0.35rem 0.7rem !important;

            transition:
                all 0.15s ease !important;
        }

        div[role="radiogroup"]
        label:hover {

            background:
                var(--rm-green-light) !important;

            border-color:
                #abc2a7 !important;
        }

        div[role="radiogroup"]
        label p {

            color:
                var(--rm-green-dark) !important;
        }


        /* =====================================================
           TOGGLE
        ===================================================== */

        [data-testid="stToggle"] label span {
            color:
                var(--rm-green-dark) !important;
        }


        /* =====================================================
           EXPANDERS
        ===================================================== */

        [data-testid="stExpander"] {

            background:
                var(--rm-card) !important;

            border:
                1px solid
                var(--rm-border) !important;

            border-radius:
                14px !important;

            overflow:
                hidden !important;
        }

        [data-testid="stExpander"] summary {

            color:
                var(--rm-green-dark) !important;

            font-weight:
                600 !important;
        }


        /* =====================================================
           DATAFRAMES / TABLES
        ===================================================== */

        [data-testid="stDataFrame"],
        .stTable {

            background:
                var(--rm-card) !important;

            border-radius:
                14px !important;

            overflow:
                hidden !important;
        }


        /* =====================================================
           CUSTOM RESCUEMESH CARDS
        ===================================================== */

        .rescue-card {

            background:
                var(--rm-card) !important;

            border:
                1px solid
                var(--rm-border) !important;

            border-left:
                5px solid
                var(--rm-green-medium) !important;

            border-radius:
                16px !important;

            padding:
                1rem 1.2rem !important;

            margin:
                0.7rem 0 !important;

            box-shadow:
                0 3px 10px
                rgba(
                    75,
                    60,
                    45,
                    0.055
                ) !important;
        }

        .rescue-card-success {

            background:
                #edf5ea !important;

            border:
                1px solid
                #c5d9c1 !important;

            border-left:
                5px solid
                var(--rm-green-medium) !important;

            border-radius:
                16px !important;

            padding:
                1rem 1.2rem !important;
        }

        .rescue-card-warning {

            background:
                var(--rm-warning-bg) !important;

            border:
                1px solid
                #dfc29e !important;

            border-left:
                5px solid
                var(--rm-warning) !important;

            border-radius:
                16px !important;

            padding:
                1rem 1.2rem !important;
        }

        .rescue-card-danger {

            background:
                var(--rm-danger-bg) !important;

            border:
                1px solid
                #d7aea5 !important;

            border-left:
                5px solid
                var(--rm-danger) !important;

            border-radius:
                16px !important;

            padding:
                1rem 1.2rem !important;
        }


        /* =====================================================
           SIDEBAR — IF USED LATER
        ===================================================== */

        [data-testid="stSidebar"] {

            background:
                #e8dac7 !important;

            border-right:
                1px solid
                var(--rm-border) !important;
        }


        /* =====================================================
           SMALL SCREEN RESPONSIVENESS
        ===================================================== */

        @media (
            max-width: 900px
        ) {

            .main .block-container,
            [data-testid="stMainBlockContainer"] {

                padding-left:
                    1rem !important;

                padding-right:
                    1rem !important;
            }
        }
        
        
        
        /* =====================================================
        FINAL FORM CONTROL OVERRIDE
        ===================================================== */

        /* SELECTBOX */
        div[data-baseweb="select"] > div {
            background-color: #FAF2E7 !important;
            color: #294936 !important;
            border-color: #294936 !important;
        }

        div[data-baseweb="select"] span,
        div[data-baseweb="select"] input {
            color: #294936 !important;
            -webkit-text-fill-color: #294936 !important;
        }


        /* NUMBER INPUT */
        [data-testid="stNumberInput"] input {
            background-color: #FAF2E7 !important;
            color: #294936 !important;
            -webkit-text-fill-color: #294936 !important;
        }


        /* TIME INPUT */
        [data-testid="stTimeInput"] input,
        input[type="time"] {
            background-color: #FAF2E7 !important;
            color: #294936 !important;
            -webkit-text-fill-color: #294936 !important;
            color-scheme: light !important;
        }


        /* TIME INPUT WRAPPERS */
        [data-testid="stTimeInput"] div[data-baseweb="input"],
        [data-testid="stTimeInput"] div[data-baseweb="base-input"],
        [data-testid="stTimeInput"] > div,
        [data-testid="stTimeInput"] > div > div {
            background-color: #FAF2E7 !important;
            color: #294936 !important;
        }


        /* KEEP ALL FORM INPUTS CREAM WHEN FOCUSED */
        input:focus,
        div[data-baseweb="select"] > div:focus-within {
            background-color: #FAF2E7 !important;
            color: #294936 !important;
        }


        /* LABELS */
        [data-testid="stSelectbox"] label,
        [data-testid="stNumberInput"] label,
        [data-testid="stTimeInput"] label {
            color: #355C43 !important;
            font-weight: 600 !important;
        }

        /* =====================================================
        DARKER DESCRIPTION / CAPTION TEXT
        ===================================================== */

        /* Streamlit captions */
        [data-testid="stCaptionContainer"],
        [data-testid="stCaptionContainer"] p,
        [data-testid="stCaptionContainer"] span {
            color: #3f5b47 !important;
            -webkit-text-fill-color: #3f5b47 !important;

            font-size: 1rem !important;
            line-height: 1.6 !important;
            font-weight: 500 !important;

            opacity: 1 !important;
        }


        /* Normal explanatory text written with st.write/st.markdown */
        [data-testid="stMarkdownContainer"] p {
            color: #3f5b47 !important;
            -webkit-text-fill-color: #3f5b47 !important;

            font-size: 1rem !important;
            line-height: 1.6 !important;

            opacity: 1 !important;
        }


        /* Slightly stronger text inside columns as well */
        [data-testid="column"] [data-testid="stCaptionContainer"] p {
            color: #3f5b47 !important;
            font-size: 0.98rem !important;
            font-weight: 500 !important;
            opacity: 1 !important;
        }
        
        
        /* =====================================================
        FINAL TYPOGRAPHY
        Larger, readable text without breaking headings
        ===================================================== */

        /* Main RescueMesh title */
        .stApp h1 {
            font-size: 3rem !important;
            line-height: 1.15 !important;
            font-weight: 800 !important;
            color: #203d2d !important;
        }


        /* Page titles: Donor Portal, Pantry Portal, etc. */
        .stApp h2 {
            font-size: 2.15rem !important;
            line-height: 1.25 !important;
            font-weight: 750 !important;
            color: #203d2d !important;
        }


        /* Section titles: Organization, Create a Donation, etc. */
        .stApp h3 {
            font-size: 1.65rem !important;
            line-height: 1.3 !important;
            font-weight: 700 !important;
            color: #294936 !important;
        }


        /* Smaller section headings */
        .stApp h4 {
            font-size: 1.3rem !important;
            font-weight: 700 !important;
            color: #294936 !important;
        }


        /* =====================================================
        NORMAL PARAGRAPH TEXT
        ===================================================== */

        [data-testid="stMarkdownContainer"] p {
            font-size: 1.08rem !important;
            line-height: 1.65 !important;
            color: #344f3c !important;
            -webkit-text-fill-color: #344f3c !important;
            opacity: 1 !important;
        }


        /* =====================================================
        CAPTIONS / DESCRIPTIONS
        ===================================================== */

        [data-testid="stCaptionContainer"],
        [data-testid="stCaptionContainer"] p,
        [data-testid="stCaptionContainer"] span {

            font-size: 1.05rem !important;
            line-height: 1.6 !important;

            color: #405d47 !important;
            -webkit-text-fill-color: #405d47 !important;

            font-weight: 500 !important;
            opacity: 1 !important;
        }


        /* =====================================================
        FORM LABELS
        ===================================================== */

        [data-testid="stSelectbox"] label,
        [data-testid="stNumberInput"] label,
        [data-testid="stTimeInput"] label,
        [data-testid="stTextInput"] label {

            font-size: 1.08rem !important;
            font-weight: 600 !important;
            color: #294936 !important;
        }


        /* =====================================================
        FORM VALUES
        ===================================================== */

        [data-testid="stSelectbox"] span,
        [data-testid="stNumberInput"] input,
        [data-testid="stTimeInput"] input,
        [data-testid="stTextInput"] input {

            font-size: 1.08rem !important;
            font-weight: 500 !important;
        }


        /* =====================================================
        METRICS
        ===================================================== */

        [data-testid="stMetricLabel"],
        [data-testid="stMetricLabel"] p {

            font-size: 1.05rem !important;
            font-weight: 600 !important;
            color: #355844 !important;
        }


        [data-testid="stMetricValue"],
        [data-testid="stMetricValue"] div {

            font-size: 2rem !important;
            font-weight: 750 !important;
            color: #294936 !important;
        }


        /* =====================================================
        NAVIGATION
        ===================================================== */

        div[role="radiogroup"] label p {

            font-size: 1.02rem !important;
            color: #294936 !important;
        }


        /* =====================================================
        BUTTONS
        ===================================================== */

        .stButton > button,
        .stFormSubmitButton > button,
        [data-testid="baseButton-primary"],
        [data-testid="baseButton-secondary"] {

            background: #5d8064 !important;

            color: #ffffff !important;
            -webkit-text-fill-color: #ffffff !important;

            font-size: 1.08rem !important;
            font-weight: 650 !important;

            min-height: 48px !important;

            border: none !important;
            border-radius: 11px !important;

            box-shadow:
                0 3px 8px
                rgba(50, 80, 55, 0.13) !important;
        }


        /* Everything inside a button stays white */
        .stButton > button *,
        .stFormSubmitButton > button *,
        [data-testid="baseButton-primary"] *,
        [data-testid="baseButton-secondary"] * {

            color: #ffffff !important;
            -webkit-text-fill-color: #ffffff !important;
        }


        .stButton > button:hover,
        .stFormSubmitButton > button:hover,
        [data-testid="baseButton-primary"]:hover,
        [data-testid="baseButton-secondary"]:hover {

            background: #355844 !important;
            color: #ffffff !important;
        }
        
        
        /* =====================================================
        FINAL FONT SIZE BOOST
        Keeps RescueMesh title as-is, enlarges rest of UI
        ===================================================== */

        /* Page headings: Donor Portal, Pantry Portal, etc. */
        .stApp h2,
        [data-testid="stMarkdownContainer"] h2 {
            font-size: 2.35rem !important;
            line-height: 1.25 !important;
            font-weight: 750 !important;
        }


        /* Section headings: Organization, Create a Donation, etc. */
        .stApp h3,
        [data-testid="stMarkdownContainer"] h3 {
            font-size: 1.85rem !important;
            line-height: 1.3 !important;
            font-weight: 700 !important;
        }


        /* Smaller headings */
        .stApp h4,
        [data-testid="stMarkdownContainer"] h4 {
            font-size: 1.45rem !important;
            line-height: 1.35 !important;
            font-weight: 700 !important;
        }


        /* Normal explanatory text */
        [data-testid="stMarkdownContainer"] p {
            font-size: 1.15rem !important;
            line-height: 1.65 !important;
        }


        /* Captions / descriptions */
        [data-testid="stCaptionContainer"],
        [data-testid="stCaptionContainer"] p,
        [data-testid="stCaptionContainer"] span {
            font-size: 1.12rem !important;
            line-height: 1.6 !important;
        }


        /* Form labels */
        [data-testid="stSelectbox"] label,
        [data-testid="stNumberInput"] label,
        [data-testid="stTimeInput"] label,
        [data-testid="stTextInput"] label {
            font-size: 1.12rem !important;
            font-weight: 600 !important;
        }


        /* Form values */
        [data-testid="stSelectbox"] span,
        [data-testid="stNumberInput"] input,
        [data-testid="stTimeInput"] input,
        [data-testid="stTextInput"] input {
            font-size: 1.12rem !important;
        }


        /* Metric labels */
        [data-testid="stMetricLabel"],
        [data-testid="stMetricLabel"] p {
            font-size: 1.12rem !important;
        }


        /* Metric numbers */
        [data-testid="stMetricValue"],
        [data-testid="stMetricValue"] div {
            font-size: 2.15rem !important;
        }


        /* Navigation labels */
        div[role="radiogroup"] label p {
            font-size: 1.08rem !important;
        }


        /* Toggle text */
        [data-testid="stToggle"] label,
        [data-testid="stToggle"] label span {
            font-size: 1.08rem !important;
        }


        /* Buttons */
        .stButton > button,
        .stFormSubmitButton > button,
        [data-testid="baseButton-primary"],
        [data-testid="baseButton-secondary"] {
            font-size: 1.12rem !important;
        }
        
        
        </style>
        """,
        unsafe_allow_html=True,
    )
    
