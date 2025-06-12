import streamlit as st
import pandas as pd
import requests
import json
import base64
from st_aggrid import AgGrid, GridOptionsBuilder
import altair as alt
import urllib.parse

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

def plot_history(df):
    """
    Plot a stacked bar chart showing initial_time and compute_time per commit date.

    Args:
        df (pd.DataFrame): DataFrame with columns ['date', 'initial_time', 'compute_time']
    """
    # Convert to long format for Altair stacking
    df_long = df.melt(id_vars=["date"], value_vars=["initial_time", "compute_time"],
                      var_name="Time Type", value_name="Time (s)")

    chart = alt.Chart(df_long).mark_bar().encode(
        x=alt.X('date:T', title='Date'),
        y=alt.Y('Time (s):Q', title='Time (seconds)'),
        color=alt.Color('Time Type:N', title='Time Type'),
        tooltip=['date:T', 'Time Type', 'Time (s)']
    ).properties(
        width=700,
        height=350,
        title="Time History per Commit"
    )

    st.altair_chart(chart, use_container_width=True)

def show_timing_chart(row):
    try:
        initial_time = float(row["initial_time"])
        compute_time = float(row["compute_time"])
        date = pd.to_datetime(row["date"])  # adjust field name if different
    except (ValueError, TypeError, KeyError):
        st.error("Missing or invalid data in row.")
        return

    # Prepare data in "long" format for Altair
    data = pd.DataFrame({
        "Time Type": ["Initial", "Compute"],
        "Time (s)": [initial_time, compute_time],
        "Date": [date, date]
    })

    chart = alt.Chart(data).mark_bar().encode(
        x=alt.X('Date:T', title='Date'),
        y=alt.Y('Time (s):Q', title='Time (seconds)'),
        color=alt.Color('Time Type:N', title='Type'),
        tooltip=['Time Type', 'Time (s)']
    ).properties(
        width=600,
        height=300,
        title="Stacked Time Breakdown"
    )

    st.altair_chart(chart, use_container_width=True)

def parse_file_history(file):
    # 1. Get commits touching the file
    commits_url = f"https://{GITLAB_ROOT}/api/v4/projects/{PROJECT_ID}/repository/commits"
    commits_params = {"path": file}
    resp = requests.get(commits_url,  params=commits_params)
    resp.raise_for_status()
    commits = resp.json()

    data = []
    for commit in commits:
        sha = commit["id"]
        commit_date = commit["committed_date"]

        # 2. Get raw JSON file content at this commit
        encoded_path = urllib.parse.quote(file, safe='')
        file_url = f"https://{GITLAB_ROOT}/api/v4/projects/{project_id}/repository/files/{encoded_path}/raw"
        file_params = {"ref": sha}

        file_resp = requests.get(file_url,  params=file_params)

        if file_resp.status_code == 200:
            try:
                json_data = file_resp.json()
                initial_time = float(json_data.get("initial_time", 0))
                compute_time = float(json_data.get("compute_time", 0))
                data.append({
                    "date": commit_date,
                    "initial_time": initial_time,
                    "compute_time": compute_time
                })
            except Exception as e:
                # Could not parse JSON or fields; skip this commit
                print(f"Skipping commit {sha} due to parse error: {e}")
        else:
            print(f"Skipping commit {sha} - file not found")

    df = pd.DataFrame(data)
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
        # Sort by date ascending
        df = df.sort_values("date")
        plot_history(df)

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
    df = df[cols]    # Configure grid options to enable single row selection
    gb = GridOptionsBuilder.from_dataframe(df)
    gb.configure_selection(selection_mode="single", use_checkbox=True)
    gridOptions = gb.build()

    # Display the grid
    grid_response = AgGrid(df, gridOptions=gridOptions, height=300, fit_columns_on_grid_load=True)
    
    # Get selected rows
    selected = grid_response.get('selected_rows', [])
    
    if  selected is not None and not selected.empty:  # True if list is non-empty
        selected_row = selected.iloc[0]
        parse_file_history (f"results/{selected_app}/{selected_row['config']}")
        # show_timing_chart(selected_row)
    else:
        st.write("Select a row to see details.")
else:
    st.info("No valid JSON files loaded.")
