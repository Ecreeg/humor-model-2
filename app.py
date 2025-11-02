import streamlit as st
from supabase import create_client
import requests
import json
import time

# -------------------- APP CONFIG --------------------
st.set_page_config(page_title="Cross-Culture Humor Mapper", page_icon="🌍", layout="centered")

# -------------------- SECRETS --------------------
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
OPENROUTER_API_KEY = st.secrets["OPENROUTER_API_KEY"]

# -------------------- FREE MODELS LIST --------------------
FREE_MODELS = [
    "mistralai/mistral-small-3.2-24b-instruct:free",
    "meta-llama/llama-3-8b-instruct:free", 
    "google/gemma-7b-it:free",
    "nousresearch/nous-hermes-2-mixtral-8x7b-dpo:free",
    "google/gemma-2b-it:free",
    "meta-llama/llama-2-13b-chat:free",
    "microsoft/wizardlm-2-8x22b:free",
    "undi95/toppy-m-7b:free"
]

# -------------------- FUNCTIONS --------------------
def get_supabase_client():
    """Create a new Supabase client for each user session."""
    return create_client(SUPABASE_URL, SUPABASE_KEY)

def signup(email, password):
    """Register a new user."""
    try:
        client = get_supabase_client()
        client.auth.sign_up({"email": email, "password": password})
        st.success("✅ Account created! Please log in now.")
    except Exception as e:
        st.error(f"❌ Signup failed: {e}")

def login(email, password):
    """Authenticate a user."""
    try:
        client = get_supabase_client()
        user_session = client.auth.sign_in_with_password({"email": email, "password": password})
        if user_session and user_session.user:
            st.session_state["logged_in"] = True
            st.session_state["user_email"] = email
            st.session_state["supabase_client"] = client
            st.toast(f"Welcome, {email}! 🎉", icon="✅")
        else:
            st.error("Invalid credentials.")
    except Exception as e:
        st.error(f"❌ Login failed: {e}")

def logout():
    """Logout the current user."""
    if "supabase_client" in st.session_state:
        try:
            st.session_state["supabase_client"].auth.sign_out()
        except Exception:
            pass
    st.session_state.clear()
    st.info("👋 Logged out successfully!")
    st.stop()

def save_translation_to_db(input_text, target_culture, translated_text, model_used):
    """Save translation to Supabase database."""
    try:
        client = st.session_state.get("supabase_client")
        if client:
            data = {
                "user_email": st.session_state["user_email"],
                "original_text": input_text,
                "target_culture": target_culture,
                "translated_text": translated_text,
                "model_used": model_used
            }
            response = client.table("humor_translations").insert(data).execute()
            return response.data
    except Exception as e:
        st.error(f"❌ Failed to save translation: {e}")
    return None

def get_user_translations():
    """Get user's previous translations."""
    try:
        client = st.session_state.get("supabase_client")
        if client:
            response = client.table("humor_translations")\
                            .select("*")\
                            .eq("user_email", st.session_state["user_email"])\
                            .order("created_at", desc=True)\
                            .limit(10)\
                            .execute()
            return response.data
    except Exception as e:
        st.error(f"❌ Failed to load history: {e}")
    return []

def smart_translate_humor(input_text, target_culture, max_attempts=3):
    """
    Use multiple free models with fallback system.
    Returns: (translated_text, model_used, attempts)
    """
    prompt = (
        f"Translate or adapt the following joke or phrase into humor suitable for {target_culture} culture. "
        f"Maintain the spirit of the joke but make it funny and understandable to that culture.\n\n"
        f"Input: {input_text}\n\nTranslated Humor:"
    )

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    attempts = []
    
    for i, model in enumerate(FREE_MODELS[:max_attempts]):
        try:
            model_name = model.split('/')[-1]
            attempts.append(f"Attempt {i+1}: {model_name}")
            
            # Show which model we're trying
            if max_attempts > 1:
                st.write(f"🔄 **Trying:** {model_name}...")
            
            body = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 500,
                "temperature": 0.7
            }

            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                data=json.dumps(body),
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                if "choices" in data:
                    translated_text = data["choices"][0]["message"]["content"]
                    
                    # Validate we got a reasonable response
                    if len(translated_text.strip()) > 10:
                        if max_attempts > 1:
                            st.success(f"✅ **Success with {model_name}!**")
                        return translated_text, model, attempts
                    else:
                        st.warning(f"❌ {model_name} returned empty response")
                        
            else:
                error_msg = f"HTTP {response.status_code}"
                if response.status_code == 429:
                    error_msg = "Rate limited"
                elif response.status_code == 503:
                    error_msg = "Service overloaded"
                
                if max_attempts > 1:
                    st.warning(f"❌ {model_name} failed ({error_msg})")
                
            # Brief pause before next attempt
            if i < max_attempts - 1:
                time.sleep(2)
                
        except requests.exceptions.Timeout:
            if max_attempts > 1:
                st.warning(f"⏰ {model_name} timed out")
            attempts.append(f"Attempt {i+1}: {model_name} - Timeout")
        except Exception as e:
            if max_attempts > 1:
                st.warning(f"❌ {model_name} error: {str(e)[:50]}...")
            attempts.append(f"Attempt {i+1}: {model_name} - Error")

    # If all models failed
    return None, None, attempts

# -------------------- UI --------------------
st.title("🌍 Cross-Culture Humor Mapper")
st.markdown("**Translate humor between cultures with AI-powered fun! 😄**")

# -------------------- AUTH SECTION --------------------
if "logged_in" not in st.session_state:
    tab_login, tab_signup = st.tabs(["🔑 Login", "Signup"])

    with tab_login:
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_password")
        if st.button("Login", use_container_width=True):
            login(email, password)

    with tab_signup:
        email = st.text_input("Email", key="signup_email")
        password = st.text_input("Password", type="password", key="signup_password")
        if st.button("Sign Up", use_container_width=True):
            signup(email, password)

else:
    st.success(f"✅ Logged in as {st.session_state['user_email']}")
    
    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("Logout", use_container_width=True):
            logout()
    with col2:
        if st.button("View History", use_container_width=True):
            st.session_state["show_history"] = True

    st.divider()
    
    # Show history if requested
    if st.session_state.get("show_history"):
        st.subheader("📜 Your Translation History")
        translations = get_user_translations()
        
        if translations:
            for i, translation in enumerate(translations):
                with st.expander(f"Translation {i+1} - {translation['target_culture']}"):
                    st.write(f"**Original:** {translation['original_text']}")
                    st.write(f"**Translated:** {translation['translated_text']}")
                    st.caption(f"Model: {translation['model_used']} | Created: {translation.get('created_at', '')}")
        else:
            st.info("No translations saved yet. Start translating below!")
        
        if st.button("Back to Translator"):
            st.session_state["show_history"] = False
        st.divider()

    # Main translator interface
    if not st.session_state.get("show_history"):
        st.subheader(" Humor Translator")
        
        # Input fields
        input_text = st.text_area(
            "Enter a joke or funny phrase:", 
            placeholder="Type something like 'Why did the chicken cross the road?'",
            height=100
        )
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            target_culture = st.text_input(
                "Target culture:", 
                placeholder="e.g., Japanese, Indian, German, Corporate, Gen Z"
            )
        
        with col2:
            max_attempts = st.selectbox("Models to try", [1, 2, 3], index=2, help="How many AI models to try if one fails")

        # Advanced options
        with st.expander("⚙️ Advanced Options"):
            save_translation = st.checkbox("Save to my history", value=True)
            show_debug = st.checkbox("Show debug information", value=False)

        # Translate button
        if st.button("Translate Humor 🎉", use_container_width=True, type="primary"):
            if not input_text or not target_culture:
                st.warning("Please fill in both fields.")
            else:
                with st.spinner("Finding the best AI model for your humor... 🤖💬"):
                    translated_text, model_used, attempts = smart_translate_humor(
                        input_text, target_culture, max_attempts
                    )
                    
                    # Display results
                    if translated_text:
                        st.success("✅ Culturally adapted humor:")
                        st.markdown(f"### {translated_text}")
			
			 		    # ---- TEXT TO SPEECH SECTION ----
   			 import streamlit.components.v1 as components

   			 # Add a speaker icon button
  			  speak_button = f"""
   			 <script>
  			  function speakText(text) {{
       			 const utterance = new SpeechSynthesisUtterance(text);
       			 utterance.lang = 'en';
      			 utterance.rate = 1.0;
        		 utterance.pitch = 1.0;
       			 speechSynthesis.speak(utterance);
   			 }}
   		 </script>
  		  <button 
       		 style="background-color:#f0f0f0;
            		   border:none;
              		   border-radius:8px;
            		   padding:8px 12px;
            		   margin-top:10px;
             		  cursor:pointer;
             		  font-size:16px;">
       			 🔊 Click to Listen
   			 </button>
    			 <script>
    			const button = document.currentScript.previousElementSibling;
    			button.addEventListener('click', () => {{
       			speakText({json.dumps(translated_text)});
   			}});
   			 </script>
   			 """

    			components.html(speak_button, height=60)

                        
                        # Show which model worked
                        if show_debug and model_used:
                            model_name = model_used.split('/')[-1]
                            st.info(f"**Model used:** {model_name}")
                        
                        # Save to database
                        if save_translation and model_used:
                            save_translation_to_db(input_text, target_culture, translated_text, 					model_used)
                            st.success("Saved to your history!")
                        
                        # Store in session state
                        st.session_state.last_translation = {
                            "original": input_text,
                            "target": target_culture,
                            "translated": translated_text,
                            "model": model_used
                        }
                        
                    else:
                        st.error("😵 All AI models failed! Here's what happened:")
                        
                        # Show detailed attempt history
                        st.write("### Attempt History:")
                        for attempt in attempts:
                            st.write(f"- {attempt}")
                        
                        st.info("""
                        **💡 What to do now:**
                        - Wait 5-10 minutes and try again
                        - Try a shorter or simpler joke
                        - Reduce the number of models to try
                        - Free AI models often get busy during peak times
                        """)

        # Debug information
        if show_debug:
            st.divider()
            st.subheader("🔧 Debug Information")
            
            st.write("**Available free models:**")
            for i, model in enumerate(FREE_MODELS[:5]):
                st.write(f"{i+1}. {model}")
            st.caption(f"... and {len(FREE_MODELS) - 5} more backup models")
            
            if 'last_translation' in st.session_state:
                st.write("**Last translation:**")
                st.json(st.session_state.last_translation)

        # Quick tips
        st.divider()
        st.subheader("💡 Quick Tips")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("**Popular Cultures:**")
            st.write("- Indian")
            st.write("- Japanese")
            st.write("- Gen Z")
            
        with col2:
            st.markdown("**Example Jokes:**")
            st.write("- 'Knock knock' jokes")
            st.write("- Puns")
            st.write("- Meme phrases")
            
        with col3:
            st.markdown("**Best Practices:**")
            st.write("- Be specific")
            st.write("- Keep it clean")
            st.write("- Have fun! 😄")

# Footer
st.markdown("---")
st.caption("Powered by multiple free AI models | Automatic fallback system | Your humor, globally understood!")