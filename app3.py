from types import new_class
import streamlit as st
from PIL import Image
import tensorflow as tf
import numpy as np
import requests
import json
from pathlib import Path
import time
import os
import hashlib
import sqlite3

# Set page config (must be first Streamlit command)
st.set_page_config(layout="wide")

# ===========================================
# AUTHENTICATION SYSTEM
# ===========================================

# Initialize SQLite database for user authentication
def init_db():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (username TEXT PRIMARY KEY, 
                  password TEXT, 
                  email TEXT)''')
    conn.commit()
    conn.close()

init_db()

# Hash password for security
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# User authentication functions
def create_user(username, password, email):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users VALUES (?, ?, ?)", 
                 (username, hash_password(password), email))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False  # Username already exists
    finally:
        conn.close()

def verify_user(username, password):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT password FROM users WHERE username=?", (username,))
    result = c.fetchone()
    conn.close()
    if result:
        return result[0] == hash_password(password)
    return False

# Authentication state
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'username' not in st.session_state:
    st.session_state.username = None

# Show login/signup forms if not authenticated
if not st.session_state.authenticated:
    st.title("Plant Health Assistant - Authentication")
    
    tab1, tab2 = st.tabs(["Login", "Sign Up"])
    
    with tab1:
        with st.form("login_form"):
            st.subheader("Login")
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            login_button = st.form_submit_button("Login")
            
            if login_button:
                if verify_user(username, password):
                    st.session_state.authenticated = True
                    st.session_state.username = username
                    st.success("Login successful!")
                    st.rerun()  # Refresh to show main app
                else:
                    st.error("Invalid username or password")
    
    with tab2:
        with st.form("signup_form"):
            st.subheader("Create Account")
            new_username = st.text_input("Choose a username")
            new_email = st.text_input("Email address")
            new_password = st.text_input("Choose a password", type="password")
            confirm_password = st.text_input("Confirm password", type="password")
            signup_button = st.form_submit_button("Sign Up")
            
            if signup_button:
                if new_password != confirm_password:
                    st.error("Passwords don't match")
                elif len(new_password) < 6:
                    st.error("Password must be at least 6 characters")
                else:
                    if create_user(new_username, new_password, new_email):
                        st.success("Account created successfully! Please login.")
                    else:
                        st.error("Username already exists")
    
    st.stop()  # Stop execution here if not authenticated

# ===========================================
# MAIN APPLICATION
# ===========================================

# Local treatment database (fallback when offline)
LOCAL_TREATMENTS = {
    'Tomato___Bacterial_spot': {
        'description': 'Caused by Xanthomonas bacteria, appears as small water-soaked spots',
        'treatment': {
            'prevention': [
                'Use disease-free seeds',
                'Practice crop rotation (2-3 years)',
                'Avoid overhead watering'
            ],
            'organic': [
                'Copper-based fungicides',
                'Bacillus subtilis products'
            ],
            'chemical': [
                'Streptomycin sulfate (limited availability)',
                'Copper hydroxide'
            ]
        }
    },
    'Tomato___Early_blight': {
        'description': 'Fungal disease causing concentric rings on leaves',
        'treatment': {
            'prevention': [
                'Remove infected plant debris',
                'Ensure proper plant spacing'
            ],
            'organic': [
                'Copper fungicides',
                'Baking soda sprays (1 tbsp/gallon)'
            ],
            'chemical': [
                'Chlorothalonil',
                'Mancozeb'
            ]
        }
    },
    'Tomato___healthy': {
        'description': 'No disease detected',
        'treatment': {
            'prevention': [
                'Maintain good growing conditions',
                'Regularly inspect plants'
            ],
            'organic': [],
            'chemical': []
        }
    }
}

# API integration for treatment info
def get_treatment_info(disease_name):
    """Get treatment info from API if online, otherwise use local database"""
    if is_online():
        try:
            response = requests.get(
                f"https://www.researchgate.net/publication/366308502_An_Automatic_Recommendation_System_for_Plant_Disease_Treatment{disease_name}",
                timeout=3
            )
            if response.status_code == 200:
                return response.json()
        except:
            pass
    
    return LOCAL_TREATMENTS.get(disease_name, {
        'description': 'No information available for this disease',
        'treatment': {
            'prevention': ['Consult local agricultural extension officer'],
            'organic': [],
            'chemical': []
        }
    })

# OFFLINE-ONLINE INFRASTRUCTURE
def is_online():
    try:
        requests.get("https://www.google.com", timeout=2)
        return True
    except:
        return False

LOCAL_DATA_PATH = Path("local_predictions.json")
os.makedirs("local_cache", exist_ok=True)

def load_local_data():
    if LOCAL_DATA_PATH.exists():
        return json.loads(LOCAL_DATA_PATH.read_text())
    return {"predictions": []}

def save_local_data(data):
    LOCAL_DATA_PATH.write_text(json.dumps(data))

def sync_predictions_to_cloud(prediction_data):
    try:
        time.sleep(1)
        return True
    except:
        return False

def get_cloud_updates():
    try:
        return {"predictions": []}
    except:
        return None

def model_prediction(test_image):
    model_path = "trained_model2.keras"
    local_cache_path = Path("local_cache/model.keras")
    
    if is_online():
        try:
            if local_cache_path.exists():
                os.remove(local_cache_path)
            import shutil
            shutil.copy(model_path, local_cache_path)
        except Exception as e:
            st.warning(f"Couldn't update model: {e}")
    
    if local_cache_path.exists():
        model = tf.keras.models.load_model(local_cache_path)
    else:
        model = tf.keras.models.load_model(model_path)
    
    image = tf.keras.preprocessing.image.load_img(test_image, target_size=(128,128))
    input_arr = tf.keras.preprocessing.image.img_to_array(image)
    input_arr = np.array([input_arr])
    prediction = model.predict(input_arr)
    return np.argmax(prediction)

# ===========================================
# MAIN PAGE LAYOUT WITH DASHBOARD
# ===========================================

# Custom CSS for the dashboard
st.markdown("""
<style>
    .dashboard-container {
        display: flex;
        flex-wrap: wrap;
        gap: 15px;
        margin-bottom: 30px;
    }
    .dashboard-item {
        flex: 1 1 200px;
        min-width: 200px;
        padding: 20px;
        border-radius: 10px;
        background-color: #f0f2f6;
        transition: all 0.3s;
        cursor: pointer;
        text-align: center;
    }
    .dashboard-item:hover {
        background-color: #e1e4eb;
        transform: translateY(-3px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
    }
    .dashboard-item.selected {
        background-color: #4a8fe7;
        color: white;
    }
    .dashboard-icon {
        font-size: 2rem;
        margin-bottom: 10px;
    }
</style>
""", unsafe_allow_html=True)

# Dashboard items
DASHBOARD_ITEMS = {
    "Home": {"icon": "🏠", "description": "Main overview"},
    "Disease Detection": {"icon": "🔍", "description": "Identify plant diseases"},
    "Pest Identification": {"icon": "🐛", "description": "Recognize common pests"},
    "Treatment Guide": {"icon": "💊", "description": "Recommended treatments"},
    "Prevention Tips": {"icon": "🛡️", "description": "Disease prevention methods"},
    "History": {"icon": "🕒", "description": "Past predictions"}
}

# Initialize session state for selected page
if 'selected_page' not in st.session_state:
    st.session_state.selected_page = "Home"

# Display dashboard in main content area
st.markdown("""<link rel="manifest" href="./manifest.json">
<meta name="mobile-web-app-capable" content="yes">
<meta name="theme-color" content="#4a8fe7">

<script>
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('./service-worker.js')
    .then(() => console.log('ServiceWorker registered'))
    .catch(() => console.log('ServiceWorker failed'));
}
</script> <h1 style='text-align: center;'>Plant Health Dashboard</h1>""", unsafe_allow_html=True)

# Create dashboard items
cols = st.columns(3)
for i, (page_name, page_info) in enumerate(DASHBOARD_ITEMS.items()):
    with cols[i % 3]:
        if st.button(
            f"{'selected' if st.session_state.selected_page == page_name else ''}"
            f"{page_info['icon']}"
            f"{page_name}"
            f"{page_info['description']}"
            f"",
            key=f"btn_{page_name}",
            use_container_width=True
        ):
            st.session_state.selected_page = page_name
            st.rerun()

# Status indicator
online_status = is_online()
st.sidebar.markdown(f"**Status:** {'Online 🌐' if online_status else 'Offline 📴'}")
st.sidebar.markdown(f"**Logged in as:** {st.session_state.username}")

# Offline/Online toggle in sidebar
st.session_state.offline_mode = st.sidebar.toggle("Offline Mode", value=False)

# ===========================================
# PAGE CONTENT
# ===========================================

def show_home():
    st.title("Welcome to Plant Health Assistant")
    st.image("background.jpg", use_container_width=True)
    st.markdown("""
    <div style='text-align: center;'>
        <h3>Comprehensive Plant Health Monitoring System</h3>
        <p>Select a function from the dashboard above to get started</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Add some featured content
    with st.expander("📌 Quick Actions", expanded=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("🔄 Check for Updates"):
                if is_online():
                    st.success("System is up to date!")
                else:
                    st.warning("Cannot check for updates - you're offline")
        
        with col2:
            if st.button("📊 View Statistics"):
                st.info("Feature coming soon!")
        
        with col3:
            if st.button("🆘 Get Help"):
                st.info("Contact support.planthealth@gmail.com")

def show_disease_detection():
    st.title("Disease Detection")
    test_image = st.file_uploader("Upload image", type=["jpg", "png","jpeg","gif"])
        
    if test_image:
        if st.button("Show Image"):
            st.image(test_image, use_column_width=60)
        
        if st.button("Predict"):
            with st.spinner("Analyzing image..."):
                result_index = model_prediction(test_image)
                
                class_name = [
                    'Tomato___Bacterial_spot',
                    'Tomato___Early_blight',
                    'Tomato___Late_blight',
                    'Tomato___Leaf_Mold',
                    'Tomato___Septoria_leaf_spot',
                    'Tomato___Spider_mites Two-spotted_spider_mite',
                    'Tomato___Target_Spot',
                    'Tomato___Tomato_Yellow_Leaf_Curl_Virus',
                    'Tomato___Tomato_mosaic_virus',
                    'Tomato___healthy'
                ]
                
                disease_name = class_name[result_index]
                treatment_info = get_treatment_info(disease_name)
                
                prediction_result = {
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "image_name": test_image.name,
                    "prediction": disease_name,
                    "synced": False,
                    "treatment_info": treatment_info
                }
                
                data = load_local_data()
                data["predictions"].append(prediction_result)
                save_local_data(data)
                
                if is_online():
                    if sync_predictions_to_cloud(prediction_result):
                        prediction_result["synced"] = True
                        data["predictions"][-1] = prediction_result
                        save_local_data(data)
                        st.balloons()
                
                st.success(f"**Disease Identified:** {disease_name}")
                
                with st.expander("🔍 Disease Details", expanded=True):
                    st.write(f"**Description:** {treatment_info['description']}")
                    
                    st.subheader("Prevention Measures")
                    for measure in treatment_info['treatment']['prevention']:
                        st.write(f"- {measure}")
                    
                    if treatment_info['treatment']['organic']:
                        st.subheader("Organic Treatments")
                        for treatment in treatment_info['treatment']['organic']:
                            st.write(f"- {treatment}")
                    
                    if treatment_info['treatment']['chemical']:
                        st.subheader("Chemical Treatments")
                        for treatment in treatment_info['treatment']['chemical']:
                            st.write(f"- {treatment}")
                
                st.info("Prediction saved locally" if not prediction_result["synced"] else "Prediction synced to cloud")

                # Feedback system
                st.markdown("---")
                with st.form("feedback_form"):
                    st.write("Was this diagnosis helpful?")
                    feedback = st.radio(
                        "Accuracy:",
                        ["Correct", "Partially correct", "Incorrect"],
                        index=None
                    )
                    notes = st.text_area("Additional notes (optional)")
                    submitted = st.form_submit_button("Submit Feedback")
                    
                    if submitted and feedback:
                        feedback_data = {
                            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                            "prediction": disease_name,
                            "feedback": feedback,
                            "notes": notes,
                            "synced": False
                        }
                        
                        if "feedback" not in data:
                            data["feedback"] = []
                        data["feedback"].append(feedback_data)
                        save_local_data(data)
                        
                        if is_online():
                            try:
                                feedback_data["synced"] = True
                                data["feedback"][-1] = feedback_data
                                save_local_data(data)
                            except:
                                pass
                        
                        st.success("Thank you for your feedback!")

def show_pest_identification():
    st.title("Pest Identification")
    st.write("This feature is currently under development.")
    st.image("https://via.placeholder.com/600x300?text=Pest+Identification", use_column_width=True)

def show_treatment_guide():
    st.title("Treatment Guide")
    st.write("Browse our comprehensive treatment guide:")
    
    disease = st.selectbox("Select a disease", list(LOCAL_TREATMENTS.keys()))
    
    if disease in LOCAL_TREATMENTS:
        treatment_info = LOCAL_TREATMENTS[disease]
        st.subheader(disease.replace("_", " "))
        
        st.write(f"**Description:** {treatment_info['description']}")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.subheader("Prevention")
            for item in treatment_info['treatment']['prevention']:
                st.write(f"- {item}")
        
        with col2:
            if treatment_info['treatment']['organic']:
                st.subheader("Organic Treatments")
                for item in treatment_info['treatment']['organic']:
                    st.write(f"- {item}")
        
        with col3:
            if treatment_info['treatment']['chemical']:
                st.subheader("Chemical Treatments")
                for item in treatment_info['treatment']['chemical']:
                    st.write(f"- {item}")

def show_prevention_tips():
    st.title("Prevention Tips")
    st.write("General prevention tips for plant diseases:")
    
    tips = [
        "🌱 Use disease-resistant plant varieties when available",
        "💧 Water plants at the base to avoid wetting foliage",
        "🌞 Ensure plants get adequate sunlight and air circulation",
        "🧤 Practice good sanitation - clean tools and remove diseased plants",
        "🔄 Rotate crops each season to prevent soil-borne diseases",
        "🔍 Regularly inspect plants for early signs of disease",
        "⚖️ Avoid over-fertilizing which can make plants more susceptible",
        "🐝 Encourage beneficial insects that prey on pests"
    ]
    
    for tip in tips:
        st.write(tip)
    
    st.image("https://via.placeholder.com/600x200?text=Healthy+Plants", use_column_width=True)

def show_history():
    st.title("Prediction History")
    data = load_local_data()
    
    if "predictions" not in data or not data["predictions"]:
        st.info("No prediction history found")
        return
    
    for prediction in reversed(data["predictions"]):
        with st.expander(f"{prediction['timestamp']} - {prediction['image_name']}"):
            st.write(f"**Prediction:** {prediction['prediction']}")
            st.write(f"**Status:** {'Synced to cloud' if prediction.get('synced', False) else 'Local only'}")
            
            if "treatment_info" in prediction:
                st.write("**Treatment Information:**")
                st.write(prediction["treatment_info"]["description"])
                
                cols = st.columns(3)
                with cols[0]:
                    st.write("**Prevention:**")
                    for item in prediction["treatment_info"]["treatment"]["prevention"]:
                        st.write(f"- {item}")
                
                with cols[1]:
                    if prediction["treatment_info"]["treatment"]["organic"]:
                        st.write("**Organic:**")
                        for item in prediction["treatment_info"]["treatment"]["organic"]:
                            st.write(f"- {item}")
                
                with cols[2]:
                    if prediction["treatment_info"]["treatment"]["chemical"]:
                        st.write("**Chemical:**")
                        for item in prediction["treatment_info"]["treatment"]["chemical"]:
                            st.write(f"- {item}")

# Page routing
if st.session_state.selected_page == "Home":
    show_home()
elif st.session_state.selected_page == "Disease Detection":
    show_disease_detection()
elif st.session_state.selected_page == "Pest Identification":
    show_pest_identification()
elif st.session_state.selected_page == "Treatment Guide":
    show_treatment_guide()
elif st.session_state.selected_page == "Prevention Tips":
    show_prevention_tips()
elif st.session_state.selected_page == "History":
    show_history()

# Logout button in sidebar
if st.sidebar.button("Logout"):
    st.session_state.authenticated = False
    st.session_state.username = None
    st.rerun()

#  link to the streamlit app is https://cropapp-kgntsy6p8fgvloc3befgbe.streamlit.app/