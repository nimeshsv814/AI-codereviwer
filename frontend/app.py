import ast
import hashlib
import os
import uuid
from datetime import datetime

import requests
import streamlit as st
from streamlit_ace import st_ace


st.set_page_config(page_title="Code Raptor", layout="wide")

AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://localhost:8001")
EXECUTION_SERVICE_URL = os.getenv("EXECUTION_SERVICE_URL", "http://localhost:8002")
AI_SERVICE_URL = os.getenv("AI_SERVICE_URL", "http://localhost:8003")
REVIEW_SERVICE_URL = os.getenv("REVIEW_SERVICE_URL", "http://localhost:8004")

MICROSERVICES = [
    {
        "name": "Auth Service",
        "base_url": AUTH_SERVICE_URL,
        "purpose": "Handles user registration and login.",
        "endpoints": [
            ("GET", "/health", "Service health check"),
            ("POST", "/register", "Create a new user"),
            ("POST", "/login", "Authenticate an existing user"),
        ],
    },
    {
        "name": "Execution Service",
        "base_url": EXECUTION_SERVICE_URL,
        "purpose": "Runs submitted Python code and returns output.",
        "endpoints": [
            ("GET", "/health", "Service health check"),
            ("POST", "/run", "Execute Python code"),
        ],
    },
    {
        "name": "AI Service",
        "base_url": AI_SERVICE_URL,
        "purpose": "Uses Gemini for code review and image-to-code extraction.",
        "endpoints": [
            ("GET", "/health", "Service health check"),
            ("POST", "/review", "Review source code"),
            ("POST", "/extract", "Extract code from an uploaded image"),
        ],
    },
    {
        "name": "Review Service",
        "base_url": REVIEW_SERVICE_URL,
        "purpose": "Stores and retrieves user review history.",
        "endpoints": [
            ("GET", "/health", "Service health check"),
            ("GET", "/reviews/{username}", "Get saved reviews for a user"),
            ("POST", "/reviews/{username}", "Save or update a review"),
            ("DELETE", "/reviews/{tab_id}", "Delete a saved review"),
        ],
    },
]


def is_valid_python_code(text):
    try:
        ast.parse(text)
        return True
    except SyntaxError:
        return False


def authenticate(username, password):
    try:
        response = requests.post(f"{AUTH_SERVICE_URL}/login", json={"username": username, "password": password})
        return response.status_code == 200
    except requests.ConnectionError:
        st.error("Auth Service is unreachable.")
        return False


def register_user(username, password):
    if not username or not password:
        return False
    try:
        response = requests.post(f"{AUTH_SERVICE_URL}/register", json={"username": username, "password": password})
        return response.status_code == 200
    except requests.ConnectionError:
        st.error("Auth Service is unreachable.")
        return False


def load_user_reviews(username):
    try:
        response = requests.get(f"{REVIEW_SERVICE_URL}/reviews/{username}")
        if response.status_code == 200:
            return response.json()
        return {}
    except requests.ConnectionError:
        st.error("Review Service is unreachable.")
        return {}


def save_review(username, tab_id, tab_data):
    if not username:
        return
    try:
        payload = {
            "id": tab_id,
            "code": tab_data["code"],
            "review_output": tab_data["review_output"],
            "run_output": tab_data["run_output"],
            "fixed_code": tab_data["fixed_code"],
            "timestamp": tab_data["timestamp"],
        }
        requests.post(f"{REVIEW_SERVICE_URL}/reviews/{username}", json=payload)
    except requests.ConnectionError:
        pass


def create_new_tab():
    new_tab_id = str(uuid.uuid4())
    st.session_state["current_tab"] = new_tab_id
    st.session_state["tabs"][new_tab_id] = {
        "code": "",
        "review_output": "",
        "run_output": "",
        "fixed_code": "",
        "editor_key": 0,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    if st.session_state.get("username"):
        save_review(st.session_state["username"], new_tab_id, st.session_state["tabs"][new_tab_id])


def delete_tab(tab_id):
    if tab_id not in st.session_state["tabs"]:
        return

    if tab_id == st.session_state["current_tab"]:
        remaining_tabs = [key for key in st.session_state["tabs"] if key != tab_id]
        if remaining_tabs:
            st.session_state["current_tab"] = remaining_tabs[0]
        else:
            create_new_tab()

    if st.session_state.get("username"):
        try:
            requests.delete(f"{REVIEW_SERVICE_URL}/reviews/{tab_id}")
        except requests.ConnectionError:
            pass

    del st.session_state["tabs"][tab_id]


def extract_code_from_image_with_genai(uploaded_image):
    try:
        files = {"file": (uploaded_image.name, uploaded_image.getvalue(), uploaded_image.type)}
        response = requests.post(f"{AI_SERVICE_URL}/extract", files=files)
        if response.status_code == 200:
            return response.json().get("extracted_code", "")
        st.error(f"Error from AI Service: {response.text}")
        return ""
    except Exception as e:
        st.error(f"Error extracting code from image: {str(e)}")
        return ""


def run_code(code, tab_id):
    try:
        response = requests.post(f"{EXECUTION_SERVICE_URL}/run", json={"code": code, "tab_id": tab_id})
        if response.status_code == 200:
            return response.json().get("output", "")
        return f"Error from Execution Service: {response.text}"
    except Exception as e:
        return f"Error: {str(e)}"


def review_code(code, tab_id):
    try:
        response = requests.post(f"{AI_SERVICE_URL}/review", json={"code": code})
        if response.status_code == 200:
            data = response.json()
            st.session_state["tabs"][tab_id]["review_output"] = data.get("review_output", "")
            if data.get("fixed_code"):
                st.session_state["tabs"][tab_id]["fixed_code"] = data.get("fixed_code")

            if st.session_state.get("username"):
                save_review(st.session_state["username"], tab_id, st.session_state["tabs"][tab_id])
        else:
            st.error(f"Error from AI Service: {response.text}")
    except Exception as e:
        st.error(f"Error during code review: {str(e)}")


def check_service_health(base_url):
    try:
        response = requests.get(f"{base_url}/health", timeout=3)
        if response.status_code == 200:
            return True, response.json()
        return False, {"status_code": response.status_code, "body": response.text}
    except requests.RequestException as e:
        return False, {"error": str(e)}


def get_sorted_tabs():
    return dict(
        sorted(
            st.session_state["tabs"].items(),
            key=lambda item: item[1]["timestamp"],
            reverse=True,
        )
    )


def init_session_state():
    if "tabs" not in st.session_state:
        st.session_state["tabs"] = {}
        create_new_tab()
    if "username" not in st.session_state:
        st.session_state["username"] = None
    if "page" not in st.session_state:
        st.session_state["page"] = "Review"


def apply_fixed_code(tab_id):
    if st.session_state["tabs"][tab_id]["fixed_code"]:
        st.session_state["tabs"][tab_id]["code"] = st.session_state["tabs"][tab_id]["fixed_code"]
        st.session_state["tabs"][tab_id]["editor_key"] += 1
        if st.session_state.get("username"):
            save_review(st.session_state["username"], tab_id, st.session_state["tabs"][tab_id])


def logout_user():
    st.session_state["username"] = None
    st.session_state["tabs"] = {}
    create_new_tab()
    st.session_state["page"] = "Login/Register"


def show_top_navigation():
    st.title("Code Raptor")
    nav_col1, nav_col2, nav_col3, nav_col4, nav_col5 = st.columns([2, 2, 2, 3, 1])

    with nav_col1:
        if st.button("Code Review", use_container_width=True):
            st.session_state["page"] = "Review"
            st.rerun()
    with nav_col2:
        if st.button("Microservices", use_container_width=True):
            st.session_state["page"] = "Microservices"
            st.rerun()
    with nav_col3:
        if st.button("About", use_container_width=True):
            st.session_state["page"] = "About"
            st.rerun()
    with nav_col4:
        st.write(f"Logged in as **{st.session_state['username']}**")
    with nav_col5:
        if st.button("Logout", use_container_width=True):
            logout_user()
            st.rerun()

    st.divider()


def show_review_history_bar():
    st.subheader("Review History")
    col1, col2 = st.columns([1, 4])

    with col1:
        if st.button("New Review", type="primary", use_container_width=True):
            create_new_tab()
            st.rerun()

    with col2:
        sorted_tabs = get_sorted_tabs()
        if not sorted_tabs:
            st.caption("No saved reviews yet.")
            return

        labels = {
            f"Review from {tab_data['timestamp']}": tab_id
            for tab_id, tab_data in sorted_tabs.items()
        }
        selected_label = st.selectbox("Open previous review", list(labels.keys()), label_visibility="collapsed")
        selected_tab = labels[selected_label]
        if selected_tab != st.session_state.get("current_tab"):
            st.session_state["current_tab"] = selected_tab
            st.rerun()


def show_about_page():
    st.title("About CodeRaptor")
    st.write(
        "CodeRaptor helps users extract code from images, run Python snippets, "
        "and get AI-powered code review feedback in one workspace."
    )

    st.subheader("Features")
    st.markdown(
        """
        - Extract code from uploaded PNG and JPG images.
        - Upload Python files directly into the editor.
        - Run Python code and view output.
        - Review code with Gemini and apply suggested fixes.
        - Save review history after login.
        """
    )

    st.subheader("Project Services")
    st.markdown(
        """
        - Frontend: Streamlit interface.
        - Auth service: login and registration.
        - Execution service: code running.
        - AI service: Gemini review and image extraction.
        - Review service: history storage.
        """
    )


def show_microservices_page():
    st.title("Microservices")
    st.write("Each backend service runs as a separate container and exposes endpoint paths over HTTP.")

    overview_rows = [
        {
            "Service": service["name"],
            "Base URL": service["base_url"],
            "Health": f'{service["base_url"]}/health',
            "Docs": f'{service["base_url"]}/docs',
        }
        for service in MICROSERVICES
    ]
    st.dataframe(overview_rows, use_container_width=True, hide_index=True)

    tabs = st.tabs([service["name"] for service in MICROSERVICES])
    for tab, service in zip(tabs, MICROSERVICES):
        with tab:
            st.subheader(service["name"])
            st.write(service["purpose"])
            st.code(service["base_url"], language="text")

            if st.button("Check Service", key=f"health_{service['name']}"):
                is_healthy, payload = check_service_health(service["base_url"])
                if is_healthy:
                    st.success("Service is reachable.")
                else:
                    st.error("Service is not reachable.")
                st.json(payload)

            st.markdown("#### Endpoint Paths")
            endpoint_rows = [
                {"Method": method, "Path": path, "Use": description}
                for method, path, description in service["endpoints"]
            ]
            st.dataframe(endpoint_rows, use_container_width=True, hide_index=True)

            st.markdown("#### FastAPI Routes")
            st.code(
                "\n".join(
                    f"{method:6} {service['base_url']}{path}"
                    for method, path, _ in service["endpoints"]
                ),
                language="text",
            )


def show_auth_page():
    st.title("Login / Register")

    if st.session_state.get("username"):
        st.session_state["page"] = "Review"
        st.rerun()
        return

    login_tab, register_tab = st.tabs(["Login", "Register"])

    with login_tab:
        username = st.text_input("Username", key="login_username")
        password = st.text_input("Password", type="password", key="login_password")
        if st.button("Login", type="primary"):
            if authenticate(username, password):
                st.session_state["username"] = username
                st.session_state["tabs"] = load_user_reviews(username)
                if not st.session_state["tabs"]:
                    create_new_tab()
                st.session_state["page"] = "Review"
                st.rerun()
            else:
                st.error("Invalid username or password")

    with register_tab:
        new_username = st.text_input("Username", key="reg_username")
        new_password = st.text_input("Password", type="password", key="reg_password")
        if st.button("Register", type="primary"):
            if register_user(new_username, new_password):
                st.success("Registration successful. Please login.")
            else:
                st.error("Username already exists or invalid input.")


def get_current_tab_data():
    if not st.session_state.get("tabs"):
        create_new_tab()

    current_tab = st.session_state.get("current_tab")
    if current_tab not in st.session_state["tabs"]:
        create_new_tab()
        current_tab = st.session_state["current_tab"]

    return current_tab, st.session_state["tabs"][current_tab]


def handle_upload(uploaded_file):
    file_type = uploaded_file.type

    if file_type == "text/x-python":
        new_code = uploaded_file.read().decode("utf-8")
        code_hash = hashlib.md5(new_code.encode()).hexdigest()

        if code_hash != st.session_state.get("last_processed_code_hash"):
            if new_code:
                tab_id = st.session_state["current_tab"]
                st.session_state["tabs"][tab_id]["code"] = new_code
                st.session_state["tabs"][tab_id]["editor_key"] += 1
                if st.session_state.get("username"):
                    save_review(st.session_state["username"], tab_id, st.session_state["tabs"][tab_id])

                st.session_state["last_processed_code_hash"] = code_hash
                st.success("Python file uploaded and code updated in the editor.")
                st.rerun()
            else:
                st.warning("No code detected in the uploaded file.")

    elif file_type in ["image/png", "image/jpeg"]:
        image_bytes = uploaded_file.getvalue()
        image_hash = hashlib.md5(image_bytes).hexdigest()

        if image_hash == st.session_state.get("last_processed_image_hash"):
            st.info("This image has already been processed.")
            return

        extracted_code = extract_code_from_image_with_genai(uploaded_file)
        if extracted_code:
            tab_id = st.session_state["current_tab"]
            if is_valid_python_code(extracted_code):
                st.session_state["tabs"][tab_id]["code"] = extracted_code
                st.session_state["tabs"][tab_id]["editor_key"] += 1
                st.success("Code extracted and updated in the editor.")
            else:
                st.session_state["tabs"][tab_id]["review_output"] = extracted_code
                st.warning("Extracted text does not seem like code. Stored in review section.")

            if st.session_state.get("username"):
                save_review(st.session_state["username"], tab_id, st.session_state["tabs"][tab_id])

            st.session_state["last_processed_image_hash"] = image_hash
            st.rerun()
        else:
            st.warning("No code detected in the uploaded image.")


def show_review_page():
    current_tab, current_tab_data = get_current_tab_data()

    st.title("Code Review")
    show_review_history_bar()

    code = st_ace(
        language="python",
        theme="monokai",
        height=300,
        value=current_tab_data["code"],
        key=f"editor_{current_tab}_{current_tab_data['editor_key']}",
    )

    uploaded_file = st.file_uploader("Upload a file (Python or Image)", type=["py", "png", "jpg", "jpeg"])
    st.caption("For images, wait while the app extracts code. To edit manually after upload, clear the uploaded file.")

    if uploaded_file is not None:
        handle_upload(uploaded_file)

    if code != current_tab_data["code"]:
        st.session_state["tabs"][current_tab]["code"] = code
        if st.session_state.get("username"):
            save_review(st.session_state["username"], current_tab, st.session_state["tabs"][current_tab])

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Run Code", key=f"run_{current_tab}", use_container_width=True):
            if code.strip():
                result = run_code(code, current_tab)
                st.session_state["tabs"][current_tab]["run_output"] = result
                if st.session_state.get("username"):
                    save_review(st.session_state["username"], current_tab, st.session_state["tabs"][current_tab])
            else:
                st.warning("Please enter some code.")

    with col2:
        if st.button("Review Code", key=f"review_{current_tab}", type="primary", use_container_width=True):
            if code.strip():
                review_code(code, current_tab)
            else:
                st.warning("Please enter some code.")

    if current_tab_data["run_output"]:
        st.markdown("#### Output")
        st.code(current_tab_data["run_output"])

    if current_tab_data["review_output"]:
        st.markdown("#### Review Feedback")
        st.markdown(current_tab_data["review_output"])

        if current_tab_data["fixed_code"]:
            if st.button("Apply Fixed Code", key=f"apply_{current_tab}"):
                apply_fixed_code(current_tab)
                st.rerun()


init_session_state()

if not st.session_state.get("username"):
    st.session_state["page"] = "Login/Register"
    show_auth_page()
else:
    show_top_navigation()

    if st.session_state["page"] == "About":
        show_about_page()
    elif st.session_state["page"] == "Microservices":
        show_microservices_page()
    else:
        show_review_page()
