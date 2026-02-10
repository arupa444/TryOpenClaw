from fastapi import FastAPI, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn
import os
import httpx
from dotenv import load_dotenv
import logging

# --- Setup ---
load_dotenv() # Load environment variables from .env file

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Configuration ---
# These should be set in your .env file for security
LINKEDIN_CLIENT_ID = os.getenv("LINKEDIN_CLIENT_ID")
LINKEDIN_CLIENT_SECRET = os.getenv("LINKEDIN_CLIENT_SECRET")
LINKEDIN_REDIRECT_URI = os.getenv("LINKEDIN_REDIRECT_URI", "http://localhost:8000/callback") # Default callback URL
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
LINKEDIN_AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
LINKEDIN_TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
LINKEDIN_PROFILE_URL = "https://api.linkedin.com/v2/me" # To get user ID and basic info
LINKEDIN_POSTS_URL_TEMPLATE = "https://api.linkedin.com/v2/ugcPosts?author={{author_urn}}" # Placeholder for fetching own posts
LINKEDIN_CREATE_POST_URL = "https://api.linkedin.com/v2/ugcPosts" # Placeholder for creating posts

# --- Gemini Integration (Placeholder) ---
# If you have a client library like google-generativeai:
# import google.generativeai as genai
# genai.configure(api_key=GEMINI_API_KEY)
# model = genai.GenerativeModel('gemini-flash-lite') # Or appropriate model name

async def generate_post_content_with_gemini(prompt: str) -> str:
    """Generates post content using Gemini Flash-Lite."""
    if not GEMINI_API_KEY:
        logging.warning("Gemini API key not set. Cannot generate content.")
        return "Gemini API key is missing. Please configure it."

    # --- Placeholder for actual Gemini API call ---
    # Replace this with your actual Gemini API client code
    try:
        # Example using httpx if no client library is available or preferred
        # This endpoint and structure are hypothetical and need to be based on actual Gemini API docs
        gemini_api_endpoint = "https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-lite:generateContent?key=" + GEMINI_API_KEY
        payload = {
            "contents": [{"parts": [{"text": prompt}]}]
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(gemini_api_endpoint, json=payload)
            response.raise_for_status()
            result = response.json()
            # Extract text from the response structure (this is hypothetical)
            if result and 'candidates' in result and result['candidates']:
                if 'content' in result['candidates'][0] and 'parts' in result['candidates'][0]['content'] and result['candidates'][0]['content']['parts']:
                    return result['candidates'][0]['content']['parts'][0]['text']
            return "Could not generate content from Gemini."
    except httpx.HTTPStatusError as e:
        logging.error(f"Gemini API error: {e} - Response: {e.response.text}")
        return f"Error generating content with Gemini: {e}"
    except Exception as e:
        logging.error(f"An unexpected error occurred with Gemini: {e}")
        return f"An unexpected error occurred with Gemini: {e}"
    # --- End Placeholder ---

async def summarize_post_with_gemini(post_text: str) -> str:
    """Summarizes post content using Gemini Flash-Lite."""
    prompt = f"Please summarize the following LinkedIn post:\n\n{post_text}"
    return await generate_post_content_with_gemini(prompt)


# --- FastAPI App ---
app = FastAPI()

# Mount static files (CSS, JS)
app.mount("/static", StaticFiles(directory="static"), name="static")
# Setup Jinja2 for templating HTML
templates = Jinja2Templates(directory="templates")

# In-memory storage for tokens (replace with a proper database for production)
# Stores {linkedin_user_id: {"access_token": "...", "author_urn": "..."}}
user_tokens = {}

# --- Helper Functions for LinkedIn API Calls ---
def get_linkedin_auth_url(): # Changed to sync as it's a simple URL construction
    """Generates the LinkedIn OAuth 2.0 authorization URL."""
    if not LINKEDIN_CLIENT_ID or not LINKEDIN_REDIRECT_URI:
        logging.error("LinkedIn Client ID or Redirect URI not configured.")
        return "/error"

    params = {
        "response_type": "code",
        "client_id": LINKEDIN_CLIENT_ID,
        "redirect_uri": LINKEDIN_REDIRECT_URI,
        "scope": "r_liteprofile r_emailaddress w_member_social", # Common scopes; adjust as needed
        "state": "some_random_string_to_prevent_csrf" # IMPORTANT: Implement proper CSRF protection
    }
    from urllib.parse import urlencode
    return f"{LINKEDIN_AUTH_URL}?{urlencode(params)}"

async def get_linkedin_access_token(code: str):
    """Exchanges an authorization code for an access token."""
    if not LINKEDIN_CLIENT_ID or not LINKEDIN_CLIENT_SECRET or not LINKEDIN_REDIRECT_URI:
        logging.error("LinkedIn credentials or Redirect URI not configured.")
        return None

    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {
        "grant_type": "authorization_code",
        "client_id": LINKEDIN_CLIENT_ID,
        "client_secret": LINKEDIN_CLIENT_SECRET,
        "redirect_uri": LINKEDIN_REDIRECT_URI,
        "code": code,
    }
    async with httpx.AsyncClient() as client:
        try:
            logging.info(f"Requesting access token from: {LINKEDIN_TOKEN_URL}")
            response = await client.post(LINKEDIN_TOKEN_URL, headers=headers, data=data)
            response.raise_for_status()
            token_data = response.json()
            logging.info("Successfully obtained access token.")
            return token_data # Should contain access_token, expires_in, etc.
        except httpx.HTTPStatusError as e:
            logging.error(f"Error getting access token: {e} - Response: {e.response.text}")
            return None
        except Exception as e:
            logging.error(f"An unexpected error occurred while getting access token: {e}")
            return None

async def get_linkedin_profile(access_token: str):
    """Fetches basic user profile information including the URN."""
    if not access_token:
        return None
    headers = {"Authorization": f"Bearer {access_token}"}
    try:
        logging.info(f"Fetching LinkedIn profile from: {LINKEDIN_PROFILE_URL}")
        async with httpx.AsyncClient() as client:
            response = await client.get(LINKEDIN_PROFILE_URL, headers=headers)
            response.raise_for_status()
            profile_data = response.json()
            logging.info(f"Successfully fetched profile: {profile_data.get('id')}")
            return profile_data # Typically contains 'id' which is needed for author_urn
    except httpx.HTTPStatusError as e:
        logging.error(f"Error fetching LinkedIn profile: {e} - Response: {e.response.text}")
        return None
    except Exception as e:
        logging.error(f"An unexpected error occurred while fetching profile: {e}")
        return None

async def create_linkedin_post(access_token: str, author_urn: str, post_content: str):
    """Creates a new post on LinkedIn."""
    if not access_token or not author_urn:
        return None

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0" # Required for LinkedIn API v2 UGC
    }
    post_body = {
        "author": author_urn,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {
                    "text": post_content
                },
                "shareMediaCategory": "NONE" # For text-only posts
            }
        },
        "visibility": {
            "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC" # 'PUBLIC' or 'CONNECTIONS'
        }
    }
    try:
        logging.info(f"Creating LinkedIn post via: {LINKEDIN_CREATE_POST_URL}")
        async with httpx.AsyncClient() as client:
            response = await client.post(LINKEDIN_CREATE_POST_URL, headers=headers, json=post_body)
            response.raise_for_status()
            post_result = response.json()
            logging.info(f"Successfully created post. Response: {post_result}")
            return post_result # Contains ID of the created post
    except httpx.HTTPStatusError as e:
        logging.error(f"Error creating LinkedIn post: {e} - Response: {e.response.text}")
        return None
    except Exception as e:
        logging.error(f"An unexpected error occurred while creating post: {e}")
        return None


async def fetch_linkedin_posts(access_token: str, author_urn: str):
    """Fetches posts by the authenticated user."""
    if not access_token or not author_urn:
        return []

    # Use the correct author URN format for the URL template
    fetch_url = LINKEDIN_POSTS_URL_TEMPLATE.format(author_urn=author_urn)
    headers = {"Authorization": f"Bearer {access_token}"}
    try:
        logging.info(f"Fetching LinkedIn posts from: {fetch_url}")
        async with httpx.AsyncClient() as client:
            response = await client.get(fetch_url, headers=headers)
            response.raise_for_status()
            posts_data = response.json()
            logging.info(f"Successfully fetched {len(posts_data.get('elements', []))} posts.")
            # The structure of posts_data.get('elements') needs to be parsed carefully
            # This is a placeholder to extract text and author info
            formatted_posts = []
            for post in posts_data.get('elements', []):
                post_text = post.get('specificContent', {}).get('com.linkedin.ugc.ShareContent', {}).get('shareCommentary', {}).get('text', 'No text available')
                timestamp = post.get('created', 'Unknown Date') # Assuming 'created' is a timestamp
                # author_urn is already known, we might fetch author name separately if needed
                formatted_posts.append({
                    "text": post_text,
                    "author_name": "You", # Placeholder, would need to fetch from profile API if not available here
                    "timestamp": timestamp
                })
            return formatted_posts
    except httpx.HTTPStatusError as e:
        logging.error(f"Error fetching LinkedIn posts: {e} - Response: {e.response.text}")
        return []
    except Exception as e:
        logging.error(f"An unexpected error occurred while fetching posts: {e}")
        return []


# --- Routes ---

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """Renders the main page, handling auth status."""
    # In a real app, you'd check for a valid session/token here.
    # For simplicity, we'll check if user_tokens has any entries.
    is_authenticated = bool(user_tokens)
    
    if not is_authenticated:
        auth_url = get_linkedin_auth_url() # Call sync function
        return templates.TemplateResponse("index.html", {"request": request, "is_authenticated": False, "auth_url": auth_url})
    
    # If authenticated, fetch posts and render page
    # Assuming we store the current user's tokens and profile info
    current_user_id = list(user_tokens.keys())[0] # Get the first user's ID
    token_info = user_tokens[current_user_id]
    access_token = token_info.get("access_token")
    author_urn = token_info.get("author_urn")

    if not access_token or not author_urn:
        logging.error("Missing access token or author URN for authenticated user.")
        # Force re-authentication if token is invalid/missing
        auth_url = get_linkedin_auth_url() # Call sync function
        return templates.TemplateResponse("index.html", {"request": request, "is_authenticated": False, "auth_url": auth_url})

    # Fetch posts using the access token
    posts = await fetch_linkedin_posts(access_token, author_urn)
    
    return templates.TemplateResponse("index.html", {"request": request, "is_authenticated": True, "posts": posts})

@app.get("/login")
async def login():
    """Redirects the user to LinkedIn for authentication."""
    auth_url = get_linkedin_auth_url() # Call sync function
    if auth_url and not auth_url.endswith("/error"):
        return RedirectResponse(auth_url)
    else:
        return HTTPException(status_code=500, detail="Failed to generate LinkedIn auth URL.")

@app.get("/callback")
async def callback(code: str = None, error: str = None, state: str = None):
    """Handles the callback from LinkedIn after authorization."""
    if error:
        logging.error(f"LinkedIn authorization error: {error}")
        return HTTPException(status_code=400, detail=f"LinkedIn authorization failed: {error}")
    
    if not code:
        logging.error("No authorization code received from LinkedIn.")
        return HTTPException(status_code=400, detail="No authorization code received.")
    
    # TODO: Verify state parameter against session for CSRF protection
    
    token_data = await get_linkedin_access_token(code)
    if not token_data or "access_token" not in token_data:
        logging.error("Failed to retrieve access token.")
        return HTTPException(status_code=500, detail="Failed to retrieve access token from LinkedIn.")
    
    access_token = token_data["access_token"]
    profile_data = await get_linkedin_profile(access_token)
    
    if not profile_data or "id" not in profile_data:
        logging.error("Failed to retrieve user profile.")
        return HTTPException(status_code=500, detail="Failed to retrieve user profile from LinkedIn.")
    
    user_id = profile_data["id"]
    author_urn = f"urn:li:person:{user_id}" # Construct the URN for posting
    
    # Store token and profile info (in-memory for this example)
    user_tokens[user_id] = {
        "access_token": access_token,
        "author_urn": author_urn,
        # "refresh_token": token_data.get("refresh_token"), # LinkedIn's token endpoint may not return refresh tokens directly
        # "expires_in": token_data.get("expires_in"),
    }
    logging.info(f"User {user_id} authenticated successfully.")
    
    # Redirect to the main page after successful login
    return RedirectResponse(url="/")

@app.post("/create_post", response_class=HTMLResponse)
async def create_post(request: Request, post_content: str = Form(...)):
    """Handles the form submission for creating a new LinkedIn post."""
    if not post_content:
        return templates.TemplateResponse("index.html", {"request": request, "error": "Post content cannot be empty.", "posts": []})

    # For now, use the first authenticated user's token
    if not user_tokens:
        logging.warning("Attempted to create post without authentication.")
        return RedirectResponse(url="/login") # Redirect to login if not authenticated

    current_user_id = list(user_tokens.keys())[0]
    token_info = user_tokens[current_user_id]
    access_token = token_info.get("access_token")
    author_urn = token_info.get("author_urn")

    if not access_token or not author_urn:
        logging.error("Missing access token or author URN for post creation.")
        return RedirectResponse(url="/login")

    # Optional: Use Gemini to enhance the post content
    # For example:
    # enhanced_content = await generate_post_content_with_gemini(f"Make this post more engaging for LinkedIn: {post_content}")
    # post_created = await create_linkedin_post(access_token, author_urn, enhanced_content)
    
    post_created = await create_linkedin_post(access_token, author_urn, post_content)

    if post_created:
        logging.info("Post created successfully.")
        # Redirect back to the main page to show updated posts
        return RedirectResponse(url="/", status_code=303) # Use 303 See Other for POST-redirect-GET
    else:
        logging.error("Failed to create post.")
        # Re-render the page with an error message
        posts = await fetch_linkedin_posts(access_token, author_urn) # Fetch posts again
        return templates.TemplateResponse("index.html", {"request": request, "error": "Failed to create post.", "posts": posts})

@app.get("/refresh_posts", response_class=HTMLResponse)
async def refresh_posts_route(request: Request):
    """Endpoint to refresh and display posts."""
    if not user_tokens:
        logging.warning("Attempted to refresh posts without authentication.")
        return RedirectResponse(url="/login")

    current_user_id = list(user_tokens.keys())[0]
    token_info = user_tokens[current_user_id]
    access_token = token_info.get("access_token")
    author_urn = token_info.get("author_urn")

    if not access_token or not author_urn:
        logging.error("Missing access token or author URN for refreshing posts.")
        return RedirectResponse(url="/login")

    posts = await fetch_linkedin_posts(access_token, author_urn)
    return templates.TemplateResponse("index.html", {"request": request, "is_authenticated": True, "posts": posts})


# --- Main Execution ---
if __name__ == "__main__":
    # To run:
    # 1. Save this code as app.py
    # 2. Create 'templates' and 'static' directories in the same folder.
    # 3. Save index.html in 'templates' and style.css, script.js in 'static'.
    # 4. Create a .env file with your LinkedIn API credentials and Gemini API key.
    # 5. Run from terminal: uvicorn app:app --reload --host 0.0.0.0 --port 8000
    #    (or use the Dockerfile provided later)
    uvicorn.run(app, host="0.0.0.0", port=8000)
