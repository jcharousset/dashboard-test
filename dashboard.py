import streamlit as st
import pandas as pd
import requests
import json
import base64

# 🔧 CONFIGURATION
NAMESPACE = "numpex-pc5/wp2-co-design"
REPO = "g5k-testing"
BRANCH = "main"
FOLDER = "results/proxy-geos-hc"
GITLAB_ROOT = "gitlab.inria.fr"

# URL-encode the project path
PROJECT_ID = "60556"

def list_subfolders(path="results"):
    url = f"https://{GITLAB_ROOT}/api/v4/projects/{PROJECT_ID}/repository/tree"
    params = {"path": path, "per_page": 100}
    r = requests.get(url, params=params)
    r.raise_for_status()
    items = r.json()
    # Filter folders only
    folders = [item["name"] for item in items if item["type"] == "tree"]
    return folders
    
# Use the full page width layout (recommended at the top of your app)
st.set_page_config(layout="wide")

st.title("📊 Benchmark Results from GitLab")

apps = list_subfolders()
if not apps:
    st.error("No app folders found under 'results'")
    st.stop()

selected_app = st.selectbox("Select an application: ", apps)
# Step 1: List files in the folder using GitLab API
tree_url = f"https://{GITLAB_ROOT}/api/v4/projects/{PROJECT_ID}/repository/tree"
params = {
    "path": f"results/{selected_app}",
    "ref": BRANCH,
    "per_page": 100,
}

file_list_resp = requests.get(tree_url, params=params)
if file_list_resp.status_code != 200:
    st.error(f"Error fetching file list: {file_list_resp.status_code}")
    st.stop()

files = file_list_resp.json()
json_files = [f["name"] for f in files if f["type"] == "blob" and f["name"].endswith(".json")]

if not json_files:
    st.warning("No JSON files found in the folder.")
    st.stop()



# Step 2: Download each JSON using raw URLs
data = []
for filename in json_files:
    raw_url = f"https://{GITLAB_ROOT}/{NAMESPACE}/{REPO}/-/raw/{BRANCH}/{FOLDER}/{filename}"
    try:
        response = requests.get(raw_url)
        response.raise_for_status()
        content = json.loads(response.text)
        content["config"] = filename
        data.append(content)
    except Exception as e:
        st.warning(f"Failed to load {filename}: {e}")

# Step 3: Display table
if data:
    df = pd.DataFrame(data)
    cols = ["config"] + [c for c in df.columns if c != "config"]
    df = df[cols]
    st.dataframe(df)
else:
    st.info("No valid JSON files loaded.")
