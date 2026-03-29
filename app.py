import streamlit as st
import subprocess
import os
import re
import yaml
import pypsa
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
import streamlit.components.v1 as components
import shutil

# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(page_title="PyPSA-DZ Control Center", page_icon="", layout="wide", initial_sidebar_state="collapsed")

WORK_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(WORK_DIR, "config.yaml")
PSN_PATH   = os.path.join(WORK_DIR, "scripts", "prepare_sector_network.py")
AEC_PATH   = os.path.join(WORK_DIR, "scripts", "add_extra_components.py")

# Resolve the result file path from the YAML config at startup
def _resolve_results_path():
  try:
    with open(CONFIG_PATH, "r") as f:
      _cfg = yaml.safe_load(f)
    _cl = _cfg.get("scenario", {}).get("clusters", [100])
    _cl = _cl[0] if isinstance(_cl, list) else _cl
    _yr = _cfg.get("scenario", {}).get("planning_horizons", [2040])
    _yr = _yr[0] if isinstance(_yr, list) else _yr
    return os.path.join(WORK_DIR, f"results/postnetworks/elec_s_{_cl}_ec_lcopt_Co2L-1h_144h_{_yr}_0.08_AB_0export.nc")
  except Exception:
    return None

RESULTS_PATH = _resolve_results_path()

# ─────────────────────────────────────────────────────────────────────────────
# GLOBAL CSS - Colors, Animations, and Inputs fixes
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Ubuntu:ital,wght@0,300;0,400;0,500;0,700;1,300;1,400;1,500;1,700&display=swap');
:root {
  --bg-deep: #F0F4F2;         /* Soft airy environmental light gray/green */
  --bg-charcoal: #E5EAE7;     /* Soft base */
  --warm-white: #FFFFFF;      /* Pure white for panels */
  --titanium-start: #FFFFFF; 
  --titanium-end: #F8FAF9; 
  --emerald: rgba(16, 185, 129, 0.25);        
  --leaf-green: #10B981;      /* Bright energetic european green */
  --t: #1E293B;               /* Crisp dark slate for text */
  --tm: #475569;              /* Soft slate for secondary text */
  --border: rgba(16, 185, 129, 0.15);
}

/* Base Typogaphy */
html, body, [class*="css"] {
  font-family: 'Ubuntu', sans-serif !important;
  background: linear-gradient(180deg, var(--bg-deep) 0%, var(--bg-charcoal) 100%) !important;
  background-attachment: fixed !important;
  color: var(--t) !important;
}

/* Animations */
@keyframes slideDown { from { opacity: 0; transform: translateY(-30px); } to { opacity: 1; transform: translateY(0); } }
@keyframes slideUp  { from { opacity: 0; transform: translateY(30px); } to { opacity: 1; transform: translateY(0); } }
@keyframes fadeIn  { from { opacity: 0; } to { opacity: 1; } }
@keyframes floatHover { 
  0% { transform: translateY(0px); box-shadow: 0 10px 25px rgba(0,0,0,0.05); } 
  100% { transform: translateY(-8px); box-shadow: 0 20px 40px rgba(16, 185, 129, 0.15); } 
}

.stApp { background: transparent !important; animation: fadeIn 0.8s ease-out; }
#MainMenu, footer, header { visibility: hidden; }

/* Dashboard Header */
.hero {
  background: var(--warm-white);
  border: 1px solid var(--border);
  border-radius: 24px;
  padding: 2.5rem 3.5rem;
  margin-bottom: 2rem;
  position: relative;
  overflow: hidden;
  animation: slideDown 0.8s cubic-bezier(0.16, 1, 0.3, 1);
  box-shadow: 0 15px 35px rgba(0,0,0,0.04);
}
.hero h1 { font-size: 3.4rem; font-weight: 800; margin: 0; color: var(--t); letter-spacing: -1px; }
.hero p { color: var(--tm); font-size: 1.3rem; margin: 0.5rem 0 0; font-weight: 500;}

/* Metric Cards - Eco Satin Metal */
.mcard {
  background: linear-gradient(145deg, var(--titanium-start) 0%, var(--titanium-end) 100%);
  border: 1px solid var(--border);
  border-radius: 20px;
  padding: 1.8rem; position: relative; overflow: hidden; 
  transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
  animation: slideUp 0.8s ease-out backwards;
  box-shadow: 0 10px 25px rgba(0,0,0,0.04);
}
.mcard:nth-child(1) { animation-delay: 0.1s; } .mcard:nth-child(2) { animation-delay: 0.2s; }
.mcard:nth-child(3) { animation-delay: 0.3s; } .mcard:nth-child(4) { animation-delay: 0.4s; }
.mcard:nth-child(5) { animation-delay: 0.5s; }

.mcard:hover { 
  animation: floatHover 0.4s forwards;
  border-color: rgba(16, 185, 129, 0.4);
}
.mcard::after { 
  content: ''; position: absolute; bottom: 0; left: 0; right: 0; height: 5px; 
  background: var(--leaf-green); opacity: 0; transition: opacity 0.3s; 
}
.mcard:hover::after { opacity: 1; }
.mcard .lbl { font-size: 0.95rem; text-transform: uppercase; letter-spacing: 0.1em; color: var(--tm); font-weight: 700; }
.mcard .val { font-size: 2.5rem; font-weight: 800; margin-top: 0.3rem; color: var(--t); }
.mcard .unit { font-size: 0.95rem; color: var(--tm); font-weight: 600; margin-top: 0.2rem;}

/* Tabs */
.stTabs [data-baseweb="tab-list"] { 
  background: transparent !important; 
  border-radius: 12px !important; 
  padding: 5px !important; 
  border: none !important;
  gap: 10px !important; 
}
.stTabs [data-baseweb="tab"] { 
  border-radius: 30px !important; 
  padding: 0.8rem 2.0rem !important; 
  font-size: 1.05rem !important; 
  font-weight: 700 !important; 
  color: var(--tm) !important; 
  background: var(--warm-white) !important; 
  border: 1px solid var(--border) !important;
  box-shadow: 0 4px 10px rgba(0,0,0,0.03) !important;
  transition: all 0.3s ease !important; 
}
.stTabs [aria-selected="true"] { 
  background: var(--leaf-green) !important; 
  color: #FFFFFF !important; 
  border-color: var(--leaf-green) !important;
  box-shadow: 0 8px 20px rgba(16, 185, 129, 0.3) !important; 
}

/* Panels */
.panel { 
  background: var(--warm-white); 
  border: 1px solid var(--border);
  border-radius: 20px; 
  padding: 2rem; margin-bottom: 2rem; 
  box-shadow: 0 10px 30px rgba(0,0,0,0.04); 
  animation: fadeIn 0.8s ease-out; 
  transition: transform 0.3s ease, box-shadow 0.3s ease;
}
.panel:hover {
  transform: translateY(-3px);
  box-shadow: 0 15px 35px rgba(0,0,0,0.07); 
}
.panel-title { font-size: 1.25rem; font-weight: 800; color: var(--t); margin-bottom: 1.5rem; display: flex; align-items: center; gap: 8px; text-transform: uppercase; letter-spacing: 0.05em; }

/* Streamlit Widgets UI Fixes */
.stSlider [data-baseweb="slider"] > div > div > div { background: var(--leaf-green) !important; }
.stSelectbox > div > div, .stNumberInput > div > div > input, .stTextInput > div > div > input {
  background: #F8FAFC !important;
  border: 1px solid rgba(16, 185, 129, 0.2) !important;
  border-radius: 12px !important;
  color: var(--t) !important;
  font-weight: 600 !important;
  font-size: 1.05rem !important;
  transition: all 0.3s;
  box-shadow: none !important;
}
.stSelectbox > div > div:hover, .stNumberInput > div > div > input:hover { 
  border-color: var(--leaf-green) !important; 
  background: #FFFFFF !important;
  box-shadow: 0 0 0 4px rgba(16, 185, 129, 0.1) !important; 
}

/* Input labels */
.stSelectbox label, .stNumberInput label, .stSlider label { color: var(--tm) !important; font-weight: 700 !important; font-size: 1.05rem !important; margin-bottom: 10px !important; letter-spacing: 0.02em; }

/* Radio labels specifically */
.stRadio label p, .stRadio div { color: var(--t) !important; font-weight: 700 !important; font-size: 1.1rem !important;}
.stRadio div[role="radiogroup"] { background: #F8FAFC !important; padding: 16px; border-radius: 16px; border: 1px solid rgba(16, 185, 129, 0.15) !important; box-shadow: inset 0 2px 4px rgba(0,0,0,0.02);}

/* Markdown & Documentation Overrides */
.stMarkdown * { color: var(--t) !important; line-height: 1.7; font-size: 1.05rem; letter-spacing: -0.01em; }
.stMarkdown h1, .stMarkdown h2, .stMarkdown h3 { color: var(--t) !important; font-weight: 800 !important; border-bottom: 2px solid var(--border); padding-bottom: 0.5rem; margin-top: 1.5rem; letter-spacing: -0.02em; }
.stMarkdown code { background-color: #F1F5F9 !important; color: var(--leaf-green) !important; padding: 4px 8px; border-radius: 6px; border: 1px solid var(--border); font-weight: 700;}
.stMarkdown pre { background-color: #F8FAFC !important; border: 1px solid var(--border); border-radius: 12px; padding: 1.5rem; box-shadow: inset 0 2px 10px rgba(0,0,0,0.02); }
.stMarkdown pre code { background-color: transparent !important; color: var(--tm) !important; border: none; font-weight: 500;}
.stMarkdown table { width: 100%; border-collapse: collapse; margin-top: 1rem; border-radius: 12px; overflow: hidden; }
.stMarkdown th, .stMarkdown td { border: 1px solid var(--border) !important; padding: 12px 16px; }
.stMarkdown th { background-color: #F8FAFC !important; font-weight: 800; color: var(--t) !important; }

/* Buttons */
.stButton > button { 
  background: var(--leaf-green) !important; 
  color: #FFFFFF !important; 
  border: none !important;
  border-radius: 30px !important; 
  padding: 1.2rem 3.2rem !important; 
  font-weight: 800 !important; 
  font-size: 1.2rem !important; 
  box-shadow: 0 8px 20px rgba(16, 185, 129, 0.3) !important; 
  transition: all 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275) !important; 
  text-transform: uppercase; 
  letter-spacing: 0.05em; 
}
.stButton > button:hover { 
  transform: translateY(-4px) !important; 
  background: #0EA5E9 !important; /* Shifts to a stunning vibrant blue! */
  box-shadow: 0 12px 25px rgba(14, 165, 233, 0.4) !important; 
}
.stButton > button:active {
  transform: translateY(2px) !important;
  box-shadow: 0 4px 10px rgba(14, 165, 233, 0.3) !important;
}

/* Glow Divider */
.glow-div { height: 2px; background: var(--border); margin: 3rem 0; border: none; border-radius: 2px; }

/* Terminal Output Area */
.stExpander { background: var(--warm-white) !important; border: 1px solid var(--border) !important; border-radius: 16px !important; box-shadow: 0 4px 15px rgba(0,0,0,0.03) !important;}
.stExpander div p { color: var(--t) !important; font-weight: 600 !important; }

/* Notifications */
.save-msg { background: #E8F5E9; border-left: 5px solid var(--leaf-green); border-radius: 8px; padding: 1.2rem 1.6rem; color: var(--t); font-weight: 700; font-size: 1.1rem; margin-bottom: 1rem; animation: slideDown 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275); box-shadow: 0 6px 15px rgba(0,0,0,0.05); }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# HELPERS: READ / WRITE TO REAL FILES
# ─────────────────────────────────────────────────────────────────────────────
def read_config():
  with open(CONFIG_PATH, "r") as f:
    return yaml.safe_load(f)

def write_config(cfg):
  with open(CONFIG_PATH, "w") as f:
    yaml.dump(cfg, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

def patch_psn(key_marker, new_value):
  """Replace a numeric value in PSN."""
  with open(PSN_PATH, "r", encoding="utf-8") as f:
    src = f.read()
  pattern = rf"({re.escape(key_marker)}\s*=\s*)[\d.]+"
  replacement = rf"\g<1>{new_value}"
  new_src, n_subs = re.subn(pattern, replacement, src)
  if n_subs == 0:
    return False
  with open(PSN_PATH, "w", encoding="utf-8") as f:
    f.write(new_src)
  return True

def patch_psn_list(list_marker, new_list_str):
  """Replace a list assignment in PSN."""
  with open(PSN_PATH, "r", encoding="utf-8") as f:
    src = f.read()
  pattern = rf"({re.escape(list_marker)}\s*=\s*)\[.*?\]"
  replacement = rf"\g<1>{new_list_str}"
  new_src, n_subs = re.subn(pattern, replacement, src)
  if n_subs == 0:
    return False
  with open(PSN_PATH, "w", encoding="utf-8") as f:
    f.write(new_src)
  return True

def patch_aec_list(list_marker, new_list_str):
  """Replace a list assignment in AEC."""
  with open(AEC_PATH, "r", encoding="utf-8") as f:
    src = f.read()
  pattern = rf"({re.escape(list_marker)}\s*=\s*)\[.*?\]"
  replacement = rf"\g<1>{new_list_str}"
  new_src, n_subs = re.subn(pattern, replacement, src)
  if n_subs == 0:
    return False
  with open(AEC_PATH, "w", encoding="utf-8") as f:
    f.write(new_src)
  return True

def patch_psn_string(key_marker, new_string):
  """Replace a string assignment in PSN."""
  with open(PSN_PATH, "r", encoding="utf-8") as f:
    src = f.read()
  pattern = rf'({re.escape(key_marker)}\s*=\s*)["\'].*?["\']'
  replacement = rf'\g<1>"{new_string}"'
  new_src, n_subs = re.subn(pattern, replacement, src)
  if n_subs == 0:
    return False
  with open(PSN_PATH, "w", encoding="utf-8") as f:
    f.write(new_src)
  return True

def patch_aec_string(key_marker, new_string):
  """Replace a string assignment in AEC."""
  with open(AEC_PATH, "r", encoding="utf-8") as f:
    src = f.read()
  pattern = rf'({re.escape(key_marker)}\s*=\s*)["\'].*?["\']'
  replacement = rf'\g<1>"{new_string}"'
  new_src, n_subs = re.subn(pattern, replacement, src)
  if n_subs == 0:
    return False
  with open(AEC_PATH, "w", encoding="utf-8") as f:
    f.write(new_src)
  return True

def patch_pypsa_costs(solar_c, solar_o, wind_c, wind_o, ely_c, ely_o, ely_eff):
  """Overwrite the economic assumptions directly into PyPSA-DZ core costs database."""
  cost_file = os.path.join(WORK_DIR, "data", "costs.csv")
  if not os.path.exists(cost_file):
    return False
  try:
    df = pd.read_csv(cost_file)
    
    # Modify Solar PV
    df.loc[(df.technology == 'solar') & (df.parameter == 'investment'), 'value'] = solar_c
    df.loc[(df.technology == 'solar') & (df.parameter == 'FOM'), 'value'] = solar_o
    
    # Modify Onshore Wind
    df.loc[(df.technology == 'onwind') & (df.parameter == 'investment'), 'value'] = wind_c
    df.loc[(df.technology == 'onwind') & (df.parameter == 'FOM'), 'value'] = wind_o
    
    # Modify Electrolyzers
    df.loc[(df.technology == 'electrolysis') & (df.parameter == 'investment'), 'value'] = ely_c
    df.loc[(df.technology == 'electrolysis') & (df.parameter == 'FOM'), 'value'] = ely_o
    df.loc[(df.technology == 'electrolysis') & (df.parameter == 'efficiency'), 'value'] = (ely_eff / 100.0)
    
    df.loc[df.technology.str.contains('electrolysis-', na=False) & (df.parameter == 'investment'), 'value'] = ely_c
    df.loc[df.technology.str.contains('electrolysis-', na=False) & (df.parameter == 'FOM'), 'value'] = ely_o
    df.loc[df.technology.str.contains('electrolysis-', na=False) & (df.parameter == 'efficiency'), 'value'] = (ely_eff / 100.0)
    
    df.to_csv(cost_file, index=False)
    return True
  except Exception as e:
    print(f"Error overriding costs.csv: {e}")
    return False

def patch_custom_coords(lat, lon):
  new_custom_str = f"custom_coords = [{lon}, {lat}]"
  
  with open(PSN_PATH, "r", encoding="utf-8") as f:
    src = f.read()
  src = re.sub(r"custom_coords\s*=\s*\[.*?\]", new_custom_str, src)
  with open(PSN_PATH, "w", encoding="utf-8") as f:
    f.write(src)
    
  with open(AEC_PATH, "r", encoding="utf-8") as f:
    src = f.read()
  src = re.sub(r"custom_coords\s*=\s*\[.*?\]", new_custom_str, src)
  with open(AEC_PATH, "w", encoding="utf-8") as f:
    f.write(src)

def read_psn_string(key_marker):
  with open(PSN_PATH, "r", encoding="utf-8") as f:
    for line in f:
      m = re.search(rf'{re.escape(key_marker)}\s*=\s*["\'](.*?)["\']', line)
      if m:
        return m.group(1)
  return "Hydrogen"

def read_psn_value(key_marker):
  with open(PSN_PATH, "r", encoding="utf-8") as f:
    for line in f:
      m = re.search(rf"{re.escape(key_marker)}\s*=\s*([\d.]+)", line)
      if m:
        return float(m.group(1))
  return None

def read_psn_list(list_marker):
  with open(PSN_PATH, "r", encoding="utf-8") as f:
    for line in f:
      m = re.search(rf"{re.escape(list_marker)}\s*=\s*(\[.*?\])", line)
      if m:
        return eval(m.group(1)) # Safe enough here 
  return []

@st.cache_resource
def load_network(path):
  if not path or not os.path.exists(path):
    return None
  try:
    return pypsa.Network(path)
  except Exception:
    return None

# ─────────────────────────────────────────────────────────────────────────────
# HERO
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero">
 <h1> PyPSA-DZ Control Center</h1>
 <p>Advanced Decision-Maker Interface — Config, Model, & Simulate the Green Hydrogen Network</p>
</div>""", unsafe_allow_html=True)

n = load_network(RESULTS_PATH)

# Compute LCOH and LCOE globally once — same formula used by Results tab and LCOS tab
_global_lcoh, _global_lcoe = 0.0, 0.0
if n is not None:
  try:
    _wt  = n.snapshot_weightings.generators
    _h2l = n.loads[n.loads.carrier.str.contains('H2', case=False, na=False)]
    _h2_mwh = sum(
      n.loads_t.p_set[ld].multiply(_wt).sum() if ld in n.loads_t.p_set.columns else n.loads.at[ld,'p_set']*_wt.sum()
      for ld in _h2l.index) if not _h2l.empty else 1
    _h2_kg = _h2_mwh * 30
    _obj   = getattr(n, 'objective', 0)
    _global_lcoh = _obj / _h2_kg if _h2_kg else 0
    _gen_mwh = n.generators_t.p.multiply(_wt, axis=0).sum().sum() if not n.generators_t.p.empty else 1
    _global_lcoe = _obj / _gen_mwh if _gen_mwh else 0
  except Exception:
    pass

# ─────────────────────────────────────────────────────────────────────────────
# TOP KPIs
# ─────────────────────────────────────────────────────────────────────────────
if n is not None:
  ts = n.generators[n.generators.carrier=='solar'].p_nom_opt.sum()
  tw = n.generators[n.generators.carrier=='onwind'].p_nom_opt.sum()
  te = n.links[n.links.carrier.str.contains('electrolysis',case=False,na=False)].p_nom_opt.sum()
  th = n.stores[n.stores.carrier.str.contains('hydrogen storage',case=False,na=False)].e_nom_opt.sum()
  obj = getattr(n,'objective',0)
  
  st.markdown('<div style="display: flex; gap: 1rem; margin-bottom: 1rem; width: 100%;">', unsafe_allow_html=True)
  kpis = [(" Solar Built",f"{ts:,.0f}","MW"),(" Wind Built",f"{tw:,.0f}","MW"),(" Electrolyzers",f"{te:,.0f}","MW"),(" H₂ Storage",f"{th:,.0f}","MWh"),(" Annual Cost",f"{obj/1e6:,.1f}","M€/yr")]
  
  cols = st.columns(5)
  for col, (lbl,val,unit) in zip(cols, kpis):
    col.markdown(f'<div class="mcard"><div class="lbl">{lbl}</div><div class="val">{val}</div><div class="unit">{unit}</div></div>', unsafe_allow_html=True)
  
  st.markdown('</div><div class="glow-div"></div>', unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# TABS
# ─────────────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([" Configure Parameters", " Network Designer", " Run Simulation", " Results Dashboard", " LCOS Comparison", " Investment Analysis", " Documentation"])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — PARAMETERS
# ══════════════════════════════════════════════════════════════════════════════
with tab1:
  st.markdown("<h3 style='font-weight: 800;'> Project Parameters</h3>", unsafe_allow_html=True)
  st.markdown("<p style='color:var(--tm); font-size:1.1rem; margin-bottom: 2rem;'>Adjust the physical and economic assumptions. Changes write directly to the simulation configuration.</p>", unsafe_allow_html=True)

  cfg = read_config()
  current_clusters = cfg.get("scenario", {}).get("clusters", [100])
  current_clusters = current_clusters[0] if isinstance(current_clusters, list) else current_clusters
  current_year   = cfg.get("scenario", {}).get("planning_horizons", [2040])[0] if isinstance(cfg.get("scenario", {}).get("planning_horizons", [2040]), list) else 2040

  cur_demand   = read_psn_value("steel_h2_demand_mw") or 460.0
  cur_active_list = read_psn_list("active_sites") or ["Tosyali", "Bellara"]
  
  if "Tosyali" in cur_active_list and "Bellara" in cur_active_list:
    site_index = 0
  elif "Tosyali" in cur_active_list:
    site_index = 1
  elif "Bellara" in cur_active_list:
    site_index = 2
  else:
    site_index = 3

  st.markdown('<div class="panel"><div class="panel-title"> Target Geolocation Mode</div>', unsafe_allow_html=True)
  f_sys_sites = st.selectbox("Select Target Geolocation Node(s):", 
      ["Both (Tosyali + Bellara AQS)", "Tosyali Only (West)", "Bellara AQS Only (East)", "Custom Point-and-Click on Map"], 
      index=site_index)

  custom_lat, custom_lon = 35.8, -0.2
  
  if f_sys_sites == "Custom Point-and-Click on Map":
    try:
      import folium
      from streamlit_folium import st_folium
      st.markdown("<p style='color:var(--warm-white); font-weight:500; margin-top:1rem;'> Click anywhere inside Algeria on the map below to drop your custom Hydrogen load plant coordinates:</p>", unsafe_allow_html=True)
      
      # Restrict Map to Algeria Boundaries ONLY
      m = folium.Map(
        location=[28.0, 3.0], 
        zoom_start=5, 
        min_zoom=5,
        tiles="CartoDB dark_matter",
        max_bounds=True,
        min_lat=18.0, max_lat=38.0,
        min_lon=-9.0, max_lon=12.0
      )
      m.add_child(folium.LatLngPopup())
      map_data = st_folium(m, height=400, use_container_width=True, key="custom_map")
      
      if map_data and map_data.get("last_clicked"):
        custom_lat = map_data["last_clicked"]["lat"]
        custom_lon = map_data["last_clicked"]["lng"]
        st.markdown(f"<div class='save-msg'> Location Locked: Data Source [{custom_lat:.4f}, {custom_lon:.4f}]. Click 'Apply' below to inject.</div>", unsafe_allow_html=True)
      else:
        st.info("Awaiting interactive ping: Please click a location on the map...")
    except ImportError:
      st.error("Missing dependency: `streamlit-folium`. Please run `pip install streamlit-folium folium` and restart.")
      
  st.markdown('</div>', unsafe_allow_html=True)

  with st.form("params_form"):
    col_a, col_b, col_c = st.columns(3)

    with col_a:
      st.markdown('<div class="panel"><div class="panel-title"> Strategy & Grid</div>', unsafe_allow_html=True)
      
      cur_mode = read_psn_string("simulation_mode") or "Hydrogen"
      m_idx = 0 if cur_mode == "Hydrogen" else 1
      f_mode = st.radio("Simulation Target Strategy", ["Hydrogen (Green Steel)", "Pure Electricity (AC Load)"], index=m_idx)
      
      f_year  = st.selectbox("Planning Year Horizon", [2030,2035,2040,2045,2050], index=[2030,2035,2040,2045,2050].index(current_year) if current_year in [2030,2035,2040,2045,2050] else 2)
      f_clusters= st.selectbox("Grid Spatial Resolution (Clusters)", [50,100,150,200,250,300], index=[50,100,150,200,250,300].index(current_clusters) if current_clusters in [50,100,150,200,250,300] else 1)
      f_dr   = st.slider("Discount Rate / WACC (%)", 4.0, 15.0, 8.0, 0.5)
      f_life  = st.slider("Project Lifetime (Years)", 10, 40, 25)
      st.markdown('</div>', unsafe_allow_html=True)

    with col_b:
      st.markdown('<div class="panel"><div class="panel-title"> Industrial Offtakers</div>', unsafe_allow_html=True)
      f_demand = st.slider("H2 Target Load (MW) [If Green Steel Mode]", 100, 1500, int(cur_demand), 10)
      
      cur_ac_demand = read_psn_value("ac_demand_mwh_yr") or 1000000.0
      f_elec_demand = st.number_input("AC Target Load (MWh/yr) [If Electricity Mode]", 10000, 10000000, int(cur_ac_demand), 50000)
      
      f_eff   = st.slider("Electrolyzer Conversion Efficiency (%)", 60, 90, 82, 1)
      f_desal  = st.number_input("Desalination Plant Yield (m3/MWh)", 100.0, 500.0, 285.0, 5.0)
      st.markdown('</div>', unsafe_allow_html=True)

    with col_c:
      st.markdown('<div class="panel"><div class="panel-title"> Base Capital Expenditures</div>', unsafe_allow_html=True)
      f_solar_c = st.number_input("Solar PV CAPEX (€/kW)", 200, 2500, 650)
      f_wind_c  = st.number_input("Onshore Wind CAPEX (€/kW)", 500, 3000, 1300)
      f_ely_c  = st.number_input("Electrolyzer CAPEX (€/kW)", 200, 3500, 600)
      f_desal_c = st.number_input("Desalination CAPEX (€/m³·h⁻¹)", 50000, 500000, 150000, 10000)
      st.markdown('</div>', unsafe_allow_html=True)

    col_d, col_e, _ = st.columns(3)
    with col_d:
      st.markdown('<div class="panel"><div class="panel-title"> Operations & Maintenance (OPEX)</div>', unsafe_allow_html=True)
      f_solar_opex = st.number_input("Solar PV OPEX (% CAPEX/yr)", 0.0, 10.0, 1.5, 0.1)
      f_wind_opex = st.number_input("Onshore Wind OPEX (% CAPEX/yr)", 0.0, 10.0, 1.4, 0.1)
      f_ely_opex  = st.number_input("Electrolyzer OPEX (% CAPEX/yr)", 0.0, 10.0, 2.5, 0.1)
      st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    submitted = st.form_submit_button(" Apply & Write Config to Disk", use_container_width=True)

  if submitted:
    messages = []
    errors  = []

    # ── 1. Write config.yaml ──
    try:
      cfg["scenario"]["clusters"]      = [f_clusters]
      cfg["scenario"]["planning_horizons"] = [f_year]
      
      # Inject OPEX / FOM if not existing
      if "costs" not in cfg: cfg["costs"] = {}
      if "fill_values" not in cfg["costs"]: cfg["costs"]["fill_values"] = {}
      cfg["costs"]["fill_values"]["FOM"] = 0 # Default fallback
      
      write_config(cfg)
      messages.append(f" Main config updated: <b>{f_clusters} Clusters</b>, Horizon <b>{f_year}</b>.")
    except Exception as e:
      errors.append(f" config.yaml failed: {e}")

    # ── 2. Patch prepare_sector_network.py ──
    try:
      target_h2_mode = "Hydrogen" if "Hydrogen" in f_mode else "Electricity"
      patch_psn_string("simulation_mode", target_h2_mode)
      patch_aec_string("simulation_mode", target_h2_mode)
      
      ok1 = patch_psn("steel_h2_demand_mw", int(f_demand))
      ok_ac = patch_psn("ac_demand_mwh_yr", int(f_elec_demand))
      okd1 = patch_psn("desalination_efficiency_m3_mwh", f_desal)
      okd2 = patch_psn("desalination_capex_eur_m3h", int(f_desal_c))
      
      # Formulate the list of active sites
      if "Both" in f_sys_sites:
        new_site_str = '["Tosyali", "Bellara"]'
      elif "Tosyali" in f_sys_sites:
        new_site_str = '["Tosyali"]'
      elif "Bellara" in f_sys_sites:
        new_site_str = '["Bellara"]'
      else:
        new_site_str = '["Custom Location"]'
        patch_custom_coords(custom_lat, custom_lon)

      ok2 = patch_psn_list("active_sites", new_site_str)
      ok3 = patch_aec_list("active_sites", new_site_str)
      
      c_ok = patch_pypsa_costs(f_solar_c, f_solar_opex, f_wind_c, f_wind_opex, f_ely_c, f_ely_opex, f_eff)
      
      if ok1 and ok2 and ok3:
        messages.append(f" Industrial nodes updated: <b>{f_sys_sites}</b> at <b>{int(f_demand)} MW</b>.")
      else:
        errors.append(" Failed to parse keys in python scripts (prepare_sector_network or add_extra_components).")
        
      if c_ok:
        messages.append(f" Core PyPSA-DZ database `costs.csv` overwritten with active UI parameters.")
      else:
        errors.append(" Failed to write to `data/costs.csv`")
        
    except Exception as e:
      errors.append(f" Network prep update failed: {e}")

    for m in messages:
      st.markdown(f'<div class="save-msg">{m}</div>', unsafe_allow_html=True)
    for e in errors:
      st.warning(e)

    crf = (f_dr/100*(1+f_dr/100)**f_life)/((1+f_dr/100)**f_life-1)
    st.info(f" System CRF = **{crf:.4f}** • Next Run Target: `elec_s_{f_clusters}_ec_lcopt_Co2L-1h_144h_{f_year}_{f_dr/100:.2f}_AB_0export.nc`")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — NETWORK DESIGNER
# ══════════════════════════════════════════════════════════════════════════════
with tab2:
  st.markdown("<h3 style='font-weight: 800;'> Dynamic Network Builder</h3>", unsafe_allow_html=True)
  st.markdown("<p style='color:var(--tm); font-size:1.05rem; margin-bottom: 1rem;'>Drag and drop components to visualize grid layouts. PyPSA-DZ code generates automatically below.</p>", unsafe_allow_html=True)

  designer_html = r"""<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@400;600;700&display=swap');
*{box-sizing:border-box;margin:0;padding:0;font-family:'Outfit',sans-serif;}
body{background:transparent;color:#e8eaf6;height:100vh;display:flex;flex-direction:column;border-radius:18px;overflow:hidden;}
#toolbar{display:flex;gap:12px;padding:16px 20px;background:rgba(0,229,255,0.05);border-bottom:1px solid rgba(0,229,255,0.15);flex-wrap:wrap;align-items:center;}
.tbtn{padding:8px 18px;border-radius:50px;border:1px solid rgba(255,255,255,.2);background:rgba(0,0,0,.4);
   color:#fff;cursor:pointer;font-size:13px;font-weight:700;transition:all .3s cubic-bezier(0.175, 0.885, 0.32, 1.275);white-space:nowrap;box-shadow: 0 4px 10px rgba(0,0,0,0.2);}
.tbtn:hover{border-color:#00e5ff; transform:translateY(-2px); box-shadow: 0 6px 15px rgba(0,229,255,0.3);}
.tbtn.active{background:linear-gradient(135deg,#00e5ff,#9d4edd);border-color:transparent;color:#fff;transform:scale(1.05);}
#clear-btn{margin-left:auto;padding:8px 18px;border-radius:50px;border:none;
      background:linear-gradient(135deg,rgba(255,107,53,0.8),rgba(200,30,30,0.8));color:#fff;cursor:pointer;font-size:13px;font-weight:700;transition:all 0.3s;}
#clear-btn:hover{transform:rotate(-3deg) scale(1.05); box-shadow: 0 0 15px rgba(255,107,53,0.5);}
#hint{padding:8px 20px;font-size:12px;color:rgba(255,255,255,.8);background:rgba(0,0,0,.6);min-height:30px; font-weight:600;}
#stage{position:relative;flex:1;overflow:hidden;cursor:crosshair;min-height:450px;
    background:radial-gradient(ellipse at 20% 30%,rgba(0,229,255,.05) 0%,transparent 60%),
         radial-gradient(ellipse at 80% 80%,rgba(157,78,221,.08) 0%,transparent 60%),
         linear-gradient(135deg,#070714 0%,#0a0a20 100%);
    box-shadow: inset 0 0 50px rgba(0,0,0,0.5);}
svg#edges{position:absolute;top:0;left:0;width:100%;height:100%;pointer-events:none}
.node{position:absolute;border-radius:50%;display:flex;align-items:center;justify-content:center;
   font-size:20px;cursor:grab;user-select:none;transition:box-shadow .3s, transform 0.2s;border:2px solid;
   background:rgba(10,10,25,0.8);backdrop-filter:blur(4px); box-shadow: 0 5px 15px rgba(0,0,0,0.5);}
.node:hover{transform:scale(1.15); z-index:100;}
.node:active{cursor:grabbing; transform:scale(1.05);}
.node-lbl{position:absolute;bottom:-24px;font-size:11px;white-space:nowrap; font-weight:700;
      color:#ffffff;left:50%;transform:translateX(-50%);pointer-events:none; text-shadow: 0 2px 4px rgba(0,0,0,0.8);}
#code-section{padding:16px 20px;background:rgba(0,0,0,.6);border-top:1px solid rgba(0,229,255,.2);height:250px;overflow-y:auto}
#code-title{font-size:13px;font-weight:800;color:#00e5ff;margin-bottom:10px; text-transform:uppercase; letter-spacing:1px;}
#code-out{font-family:'JetBrains Mono','Courier New',monospace;font-size:12px;color:#00ff88;white-space:pre;line-height:1.6;}
.keyword{color:#00e5ff;} .string{color:#ffaa00;}
</style></head><body>

<div id="toolbar">
 <button class="tbtn active" onclick="setTool('bus',this)"> AC Bus Point</button>
 <button class="tbtn" onclick="setTool('h2bus',this)"> H₂ Hub</button>
 <button class="tbtn" onclick="setTool('solar',this)"> Solar Farm</button>
 <button class="tbtn" onclick="setTool('wind',this)"> Wind Farm</button>
 <button class="tbtn" onclick="setTool('load',this)"> Steel Offtaker</button>
 <button class="tbtn" onclick="setTool('electrolyzer',this)"> Electrolyzer</button>
 <button class="tbtn" onclick="setTool('storage',this)"> H₂ Storage</button>
 <button class="tbtn" onclick="setTool('link',this)"> Line Connect</button>
 <button id="clear-btn" onclick="clearAll()"> Sweep Clean</button>
</div>
<div id="hint"> Click the canvas to instantiate a component.</div>
<div id="stage"><svg id="edges"></svg></div>
<div id="code-section">
 <div id="code-title"> Code Generation Sync</div>
 <div id="code-out"># Awaiting node placement...</div>
</div>

<script>
const COLORS={bus:'#00e5ff',h2bus:'#9d4edd',solar:'#ffaa00',wind:'#00e5ff',load:'#ff5555',electrolyzer:'#ff00ff',storage:'#00ff88'};
const ICONS ={bus:'',h2bus:'H₂',solar:'',wind:'',load:'',electrolyzer:'',storage:''};
const SIZE ={bus:56,h2bus:56,solar:48,wind:48,load:48,electrolyzer:48,storage:48};

let tool='bus', nodes=[], edges=[], linkSrc=null, counters={};
const stage=document.getElementById('stage');
const svg =document.getElementById('edges');
const hint =document.getElementById('hint');
const codeOut=document.getElementById('code-out');

function setTool(t,btn){
 tool=t; linkSrc=null;
 document.querySelectorAll('.tbtn').forEach(b=>b.classList.remove('active'));
 btn.classList.add('active');
 document.querySelectorAll('.node').forEach(n=>n.style.outline='none');
 hint.textContent=t==='link'?' Click SOURCE component then TARGET component to weave a line.':' Canvas ready. Click anywhere to drop a '+t+'.';
}

function clearAll(){
 nodes=[]; edges=[]; counters={}; linkSrc=null;
 stage.querySelectorAll('.node').forEach(n=>n.remove());
 renderEdges(); generateCode();
}

stage.addEventListener('click',function(e){
 if(e.target.closest('.node')) return;
 if(tool==='link') return;
 const r=stage.getBoundingClientRect();
 addNode(tool, e.clientX-r.left, e.clientY-r.top);
});

function addNode(type,cx,cy){
 counters[type]=(counters[type]||0)+1;
 const id=type+'_'+counters[type];
 const label=type.toUpperCase()+'_'+counters[type];
 const sz=SIZE[type];
 nodes.push({id,type,label,cx,cy});

 const el=document.createElement('div');
 el.className='node';
 el.id='nd_'+id;
 el.dataset.id=id;
 el.style.cssText=`width:${sz}px;height:${sz}px;left:${cx-sz/2}px;top:${cy-sz/2}px;color:${COLORS[type]};border-color:${COLORS[type]};box-shadow:0 0 20px ${COLORS[type]}66;`;
 el.innerHTML=`${ICONS[type]}<span class="node-lbl">${label}</span>`;

 let drag=false,ox=0,oy=0;
 el.addEventListener('mousedown',function(e){
  if(tool==='link') return;
  drag=true; ox=e.offsetX; oy=e.offsetY;
  e.preventDefault();
 });
 document.addEventListener('mousemove',function(e){
  if(!drag) return;
  const r=stage.getBoundingClientRect();
  const nx=Math.max(sz/2,Math.min(r.width-sz/2, e.clientX-r.left-ox+sz/2));
  const ny=Math.max(sz/2,Math.min(r.height-sz/2, e.clientY-r.top-oy+sz/2));
  el.style.left=(nx-sz/2)+'px';
  el.style.top =(ny-sz/2)+'px';
  const nd=nodes.find(n=>n.id===id);
  if(nd){nd.cx=nx;nd.cy=ny;}
  renderEdges();
 });
 document.addEventListener('mouseup',()=>drag=false);

 el.addEventListener('click',function(e){
  e.stopPropagation();
  if(tool!=='link') return;
  if(!linkSrc){
   linkSrc=id;
   el.style.outline=`3px solid #fff`;
   hint.textContent=' Source: '+label+'. Click the destination node.';
  } else if(linkSrc!==id){
   edges.push({from:linkSrc,to:id});
   document.querySelectorAll('.node').forEach(n=>n.style.outline='none');
   linkSrc=null;
   hint.textContent=' Connection fused! Continue linking or switch tools.';
   renderEdges(); generateCode();
  }
 });

 stage.appendChild(el);
 generateCode();
}

function renderEdges(){
 svg.innerHTML='';
 edges.forEach(function(e){
  const f=nodes.find(n=>n.id===e.from), t=nodes.find(n=>n.id===e.to);
  if(!f||!t) return;
  const line=document.createElementNS('http://www.w3.org/2000/svg','line');
  line.setAttribute('x1',f.cx); line.setAttribute('y1',f.cy);
  line.setAttribute('x2',t.cx); line.setAttribute('y2',t.cy);
  line.setAttribute('stroke','rgba(255,255,255,0.4)');
  line.setAttribute('stroke-width','3');
  line.setAttribute('stroke-dasharray','8 6');
  svg.appendChild(line);
  
  const mx=(f.cx+t.cx)/2, my=(f.cy+t.cy)/2;
  const angle=Math.atan2(t.cy-f.cy,t.cx-f.cx)*180/Math.PI;
  const poly=document.createElementNS('http://www.w3.org/2000/svg','polygon');
  poly.setAttribute('points','-8,-5 8,0 -8,5');
  poly.setAttribute('fill','#00e5ff');
  poly.setAttribute('transform','translate('+mx+','+my+') rotate('+angle+')');
  svg.appendChild(poly);
 });
}

function generateCode(){
 const buses=nodes.filter(n=>n.type==='bus'), h2buses=nodes.filter(n=>n.type==='h2bus');
 const solars=nodes.filter(n=>n.type==='solar'), winds=nodes.filter(n=>n.type==='wind');
 const loads=nodes.filter(n=>n.type==='load'), elys=nodes.filter(n=>n.type==='electrolyzer');
 const stors=nodes.filter(n=>n.type==='storage');
 
 let code='<span class="keyword">import</span> pypsa\n<span class="keyword">import</span> pandas <span class="keyword">as</span> pd\n\nn = pypsa.Network()\nn.set_snapshots(pd.date_range(<span class="string">"2040-01-01"</span>, periods=8760, freq=<span class="string">"h"</span>))\n\n';
 
 if(buses.length){ buses.forEach(b=>code+=`n.add(<span class="string">"Bus"</span>, <span class="string">"${b.label}"</span>, carrier=<span class="string">"AC"</span>)\n`); code+='\n'; }
 if(h2buses.length){ h2buses.forEach(b=>code+=`n.add(<span class="string">"Bus"</span>, <span class="string">"${b.label}"</span>, carrier=<span class="string">"H2"</span>)\n`); code+='\n'; }
 
 if(solars.length){
  const bus0=buses[0]?buses[0].label:'AC_BUS_1';
  solars.forEach(s=>code+=`n.add(<span class="string">"Generator"</span>, <span class="string">"${s.label}"</span>, bus=<span class="string">"${bus0}"</span>, carrier=<span class="string">"solar"</span>, p_nom_extendable=<span class="keyword">True</span>)\n`);
  code+='\n';
 }
 if(winds.length){
  const bus0=buses[0]?buses[0].label:'AC_BUS_1';
  winds.forEach(w=>code+=`n.add(<span class="string">"Generator"</span>, <span class="string">"${w.label}"</span>, bus=<span class="string">"${bus0}"</span>, carrier=<span class="string">"onwind"</span>, p_nom_extendable=<span class="keyword">True</span>)\n`);
  code+='\n';
 }
 if(loads.length){
  const bus0=h2buses[0]?h2buses[0].label:(buses[0]?buses[0].label:'BUS_1');
  loads.forEach(l=>code+=`n.add(<span class="string">"Load"</span>, <span class="string">"${l.label}"</span>, bus=<span class="string">"${bus0}"</span>, carrier=<span class="string">"H2"</span>, p_set=460)\n`);
  code+='\n';
 }
 if(elys.length){
  const b0=buses[0]?buses[0].label:'AC_1', b1=h2buses[0]?h2buses[0].label:'H2_1';
  elys.forEach(e=>code+=`n.add(<span class="string">"Link"</span>, <span class="string">"${e.label}"</span>, bus0=<span class="string">"${b0}"</span>, bus1=<span class="string">"${b1}"</span>, carrier=<span class="string">"electrolysis"</span>, p_nom_extendable=<span class="keyword">True</span>)\n`);
  code+='\n';
 }
 if(stors.length){
  const bus0=h2buses[0]?h2buses[0].label:(buses[0]?buses[0].label:'BUS_1');
  stors.forEach(s=>code+=`n.add(<span class="string">"Store"</span>, <span class="string">"${s.label}"</span>, bus=<span class="string">"${bus0}"</span>, carrier=<span class="string">"H2 Storage"</span>, e_nom_extendable=<span class="keyword">True</span>)\n`);
  code+='\n';
 }
 if(edges.length){
  edges.forEach(function(edge){
   const f=nodes.find(n=>n.id===edge.from), t=nodes.find(n=>n.id===edge.to);
   if(f&&t) code+=`n.add(<span class="string">"Line"</span>, <span class="string">"${f.label}-${t.label}"</span>, bus0=<span class="string">"${f.label}"</span>, bus1=<span class="string">"${t.label}"</span>)\n`;
  });
  code+='\n';
 }
 if(nodes.length>0) code+='<span class="keyword"># Execution triggers\n</span>n.optimize(solver_name=<span class="string">"highs"</span>)';
 codeOut.innerHTML=code;
}
generateCode();
</script></body></html>"""

  components.html(designer_html, height=800, scrolling=False)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — SIMULATE
# ══════════════════════════════════════════════════════════════════════════════
with tab3:
  st.markdown("<h3 style='font-weight: 800;'> Orchestrate Execution</h3>", unsafe_allow_html=True)
  cfg2 = read_config()
  cl  = cfg2.get("scenario", {}).get("clusters", [100])
  cl  = cl[0] if isinstance(cl, list) else cl
  yr  = cfg2.get("scenario", {}).get("planning_horizons", [2040])
  yr  = yr[0] if isinstance(yr, list) else yr
  target_nc = f"results/postnetworks/elec_s_{cl}_ec_lcopt_Co2L-1h_144h_{yr}_0.08_AB_0export.nc"

  col1, col2 = st.columns([1.2, 1])

  with col1:
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown('<div class="panel-title"> Model Target Overview</div>', unsafe_allow_html=True)
    st.markdown(f"<p style='font-size:1.1rem;'><b>Clusters:</b> <span style='color:var(--p);'>{cl}</span> &nbsp;|&nbsp; <b>Horizon:</b> <span style='color:var(--s);'>{yr}</span></p>", unsafe_allow_html=True)
    
    cur_dem = read_psn_value('steel_h2_demand_mw') or 460
    sts = read_psn_list("active_sites") or ["Tosyali", "Bellara"]
    st.markdown(f"<p style='font-size:1.1rem;'><b>Nodes:</b> {', '.join(sts)} &nbsp;|&nbsp; <b>Demand:</b> <span style='color:var(--p);'>{cur_dem:.0f} MW</span> ea.</p>", unsafe_allow_html=True)
    
    st.code(target_nc, language="bash")
    st.markdown('</div>', unsafe_allow_html=True)

  with col2:
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown('<div class="panel-title"> Compute Matrix Setup</div>', unsafe_allow_html=True)
    max_cores = os.cpu_count() or 4
    n_jobs = st.slider("Parallel Threads (Snakemake Cores)", 1, max_cores, max_cores)
    force = st.checkbox("Force full network rebuild (ignore caches)", False)
    st.markdown('</div>', unsafe_allow_html=True)

  st.markdown('<div class="glow-div"></div>', unsafe_allow_html=True)

  if st.button(" Calculate", use_container_width=True):
    # ── Archive Previous Results ──
    res_dir = os.path.join(WORK_DIR, "results")
    if os.path.exists(res_dir) and not force:
      run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
      prev_dir = os.path.join(WORK_DIR, "prevResults", f"run_{run_id}")
      os.makedirs(prev_dir, exist_ok=True)
      for item in os.listdir(res_dir):
        s = os.path.join(res_dir, item)
        d = os.path.join(prev_dir, item)
        try:
          if os.path.isdir(s):
            shutil.copytree(s, d, dirs_exist_ok=True)
            shutil.rmtree(s)
          else:
            shutil.copy2(s, d)
            os.remove(s)
        except Exception as e:
          print(f"Failed to archive {item}: {e}")
          pass

    ff = "--forceall" if force else ""
    unlock_cmd = 'conda run -n pypsa-earth snakemake --unlock'
    cmd = f'conda run -n pypsa-earth snakemake -j {n_jobs} {ff} "{target_nc}"'
    with st.expander(" Terminal Telemetry Pipeline", expanded=True):
      status_text = st.empty()
      progress_bar = st.progress(0)
      log_container = st.empty()
      status_text.markdown("**Unlocking directory and compiling Model DAG... Please standby...**")
      
      # Unlock the snakemake directory to prevent LockExceptions
      subprocess.run(unlock_cmd, shell=True, cwd=WORK_DIR)
      
      import time
      env = os.environ.copy()
      env["PYTHONUNBUFFERED"] = "1"
      p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd=WORK_DIR, bufsize=1, env=env)
      
      full_log = []
      last_update = time.time()
      
      for line in p.stdout:
        full_log.append(line)
        
        m = re.search(r'(\d+)\s+of\s+(\d+)\s+steps\s+\(([\d]+)%\)\s+done', line)
        if m:
          pct = int(m.group(3))
          progress_bar.progress(pct)
          status_text.markdown(f"**Progress:** {pct}% - {m.group(1)}/{m.group(2)} steps")
          log_container.code("".join(full_log[-25:]), language="bash") # Force update on progress step
          last_update = time.time()
          
        # Throttled terminal streaming: Update UI only twice a second to prevent browser websocket freezing
        elif time.time() - last_update > 0.5:
          log_container.code("".join(full_log[-25:]), language="bash")
          last_update = time.time()
      
      p.wait()
      log_container.code("".join(full_log[-25:]), language="bash") # Final flush
      
    if p.returncode == 0:
      progress_bar.progress(100)
      status_text.markdown("**Progress:** 100% - Simulation Complete")
      st.success(" Execution sequence finalized! Proceed to Dashboard tab.")
      st.cache_resource.clear()
      st.rerun()
    else:
      st.error(" Fatal disruption in generation logic.")
      st.code("".join(full_log[-50:]), language="bash")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — RESULTS
# ══════════════════════════════════════════════════════════════════════════════
with tab4:
  st.markdown("<h3 style='font-weight: 800;'> Post-Flight Analytics</h3>", unsafe_allow_html=True)
  n_res = None
  err_msg = ""
  try:
      n_res = pypsa.Network(os.path.join(WORK_DIR, target_nc))
  except Exception as e:
      err_msg = str(e)

  if n_res is None:
    st.markdown(f'<div class="panel" style="text-align:center;padding:4rem"><div style="font-size:4rem"></div><div style="color:var(--tm);margin-top:1rem;font-size:1.2rem;font-weight:600;">Neural sync pending... Run a simulation to establish telemetry link.</div><br/><p style="color:red"><b>Network Load Error:</b> {err_msg}</p></div>', unsafe_allow_html=True)

  else:
    n = n_res  # expose to rest of tab scope
    obj  = getattr(n, 'objective', 0)
    dr_  = 0.08
    lt_  = 25
    crf_ = (dr_*(1+dr_)**lt_)/((1+dr_)**lt_-1)
    npc  = obj / crf_
    
    wt = n.snapshot_weightings.generators if hasattr(n,'snapshot_weightings') else pd.Series(1,index=n.snapshots)
    
    # Financial breakdowns
    cap_fom_annual = 0
    var_opex_annual = 0
    elec_gen_mwh = 0
    
    for c in n.generators.carrier.unique():
      idx = n.generators[n.generators.carrier==c].index
      cap_fom_annual += (n.generators.p_nom_opt[idx] * n.generators.capital_cost[idx]).sum()
      if not n.generators_t.p.empty and len(idx.intersection(n.generators_t.p.columns)):
        gen_mwh = n.generators_t.p[idx].multiply(wt, axis=0).sum().sum()
        elec_gen_mwh += gen_mwh
        var_opex_annual += (n.generators_t.p[idx].multiply(wt, axis=0).sum() * n.generators.marginal_cost[idx]).sum()

    for c in n.links.carrier.unique():
      idx = n.links[n.links.carrier==c].index
      cap_fom_annual += (n.links.p_nom_opt[idx] * n.links.capital_cost[idx]).sum()
    for c in n.stores.carrier.unique():
      idx = n.stores[n.stores.carrier==c].index
      cap_fom_annual += (n.stores.e_nom_opt[idx] * n.stores.capital_cost[idx]).sum()

    h2l = n.loads[n.loads.carrier.str.contains('H2',case=False,na=False)]
    h2_mwh = sum(
      n.loads_t.p_set[ld].multiply(wt).sum() if ld in n.loads_t.p_set.columns else n.loads.at[ld,'p_set']*wt.sum()
      for ld in h2l.index) if not h2l.empty else 1
      
    h2_kg = h2_mwh * 30 # Approximation (33.33 kWh/kg LHV, typically scaled 30 for system sizing here)
    lcoh = obj / h2_kg if h2_kg else 0
    lcoe = obj / elec_gen_mwh if elec_gen_mwh else 0

    # LCOS — Bhaskar et al. LCOP formula (same as LCOS Comparison tab, default parameters)
    _r, _n = 0.08, 25
    _acc   = (_r * (1 + _r)**_n) / ((1 + _r)**_n - 1)   # annuity factor
    _capex_t        = 600.0   # EUR/t capacity (DRI-EAF plant)
    _maint_pct      = 0.03
    _labor_t        = 65.0    # EUR/t
    _ore_price      = 130.0   # EUR/t pellets
    _h2_cons        = 86.89   # kg H2 / t_steel
    _eaf_elec       = 0.70    # MWh / t_steel
    _grid_elec      = 20.68   # EUR/MWh (Algerian grid)
    _co2_h2dri      = 0.05    # t CO2 / t_steel
    _cbam_factor    = 0.485   # 2030 phase-in schedule
    _ets_price      = 75.0    # EUR/t CO2
    lcos = (
      _capex_t * _acc * 1.10          # plant CAPEX annuity (H2-shaft premium)
      + _capex_t * _maint_pct         # maintenance
      + _labor_t                       # labour & fixed ops
      + _ore_price * 1.45             # iron ore (1.45 t ore / t_steel)
      + _eaf_elec * _grid_elec        # EAF electricity
      + _h2_cons * lcoh               # green hydrogen reductant
      + _co2_h2dri * _cbam_factor * _ets_price  # CBAM carbon tax (2030 default)
    )

    st.markdown('<div style="display: flex; gap: 1rem; width: 100%; flex-wrap: wrap;">', unsafe_allow_html=True)
    c1,c2,c3,c4,c5,c6 = st.columns(6)
    c1.markdown(f'<div class="mcard" style="box-shadow: inset 0 0 20px rgba(0,229,255,0.1);"><div class="lbl"> Total Annualized CAPEX & FOM</div><div class="val">{cap_fom_annual/1e6:,.1f}</div><div class="unit">M€ / year</div></div>', unsafe_allow_html=True)
    c2.markdown(f'<div class="mcard" style="box-shadow: inset 0 0 20px rgba(255,170,0,0.1);"><div class="lbl"> Total Variable OPEX</div><div class="val">{var_opex_annual/1e6:,.2f}</div><div class="unit">M€ / year</div></div>', unsafe_allow_html=True)
    c3.markdown(f'<div class="mcard" style="box-shadow: inset 0 0 20px rgba(157,78,221,0.1);"><div class="lbl"> Realized Net Present Cost</div><div class="val">{npc/1e9:,.2f}</div><div class="unit">Billion € (Lifetime)</div></div>', unsafe_allow_html=True)
    c4.markdown(f'<div class="mcard" style="box-shadow: inset 0 0 20px rgba(0,255,136,0.1);"><div class="lbl"> Levelized Cost of Energy</div><div class="val">{lcoe:,.2f}</div><div class="unit">€ / MWh (LCOE)</div></div>', unsafe_allow_html=True)
    c5.markdown(f'<div class="mcard" style="box-shadow: inset 0 0 20px rgba(255,85,85,0.1);"><div class="lbl"> Derived Price H₂</div><div class="val">{lcoh:.2f}</div><div class="unit">€ / kg (LCOH)</div></div>', unsafe_allow_html=True)
    c6.markdown(f'<div class="mcard" style="box-shadow: inset 0 0 20px rgba(254,215,170,0.1);"><div class="lbl"> Final Cost Of Green Steel</div><div class="val">{lcos:,.0f}</div><div class="unit">€ / Tonne (LCOS)</div></div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    st.info(" **Component Replacement Note:** PyPSA-DZ uses the _Equivalent Annual Cost_ method. If a PV farm lasts 25 years but the project horizon modeled is 40 years, the optimizer seamlessly models the asset by charging an annualized annuity spanning your entire project without demanding a distinct mid-project 'replacement year' lump sum. The continuous mathematical amortization handles discrepancies between project lifetimes and individual asset lifetimes perfectly!")

    st.markdown('<div class="glow-div"></div>', unsafe_allow_html=True)

    def allowed_component(c):
      name = str(c).lower()
      return any(k in name for k in ['solar', 'wind', 'electrolysis', 'storage', 'desalination', 'pipeline']) and ('battery' not in name) and ('co2' not in name)
      
    # --- ROW 1: ENERGY MIX & CAPEX DISTRIBUTION ---
    st.markdown('<div class="glow-div"></div>', unsafe_allow_html=True)
    col_p, col_g = st.columns(2)
    with col_p:
      st.markdown("<div class='panel'><div class='panel-title'>Total Capital Outlay Distribution</div>", unsafe_allow_html=True)
      cap_d = {}
      for c in n.generators.carrier.unique():
        if allowed_component(c):
          v=(n.generators.p_nom_opt[n.generators.carrier==c]*n.generators.capital_cost[n.generators.carrier==c]).sum()
          if v>1: cap_d[c]=v
      for c in n.links.carrier.unique():
        if allowed_component(c):
          v=(n.links.p_nom_opt[n.links.carrier==c]*n.links.capital_cost[n.links.carrier==c]).sum()
          if v>1: cap_d[c]=v
      for c in n.stores.carrier.unique():
        if allowed_component(c):
          v=(n.stores.e_nom_opt[n.stores.carrier==c]*n.stores.capital_cost[n.stores.carrier==c]).sum()
          if v>1: cap_d[c]=v
      if cap_d:
        df_c=pd.DataFrame(list(cap_d.items()),columns=['Component','CAPEX (EUR)'])
        fig=px.pie(df_c,values='CAPEX (EUR)',names='Component',color_discrete_sequence=['#10B981','#0EA5E9','#F59E0B','#8B5CF6','#EF4444'],hole=.5)
        fig.update_layout(paper_bgcolor='rgba(0,0,0,0)',plot_bgcolor='rgba(0,0,0,0)',font_color='#1E293B',margin=dict(l=5,r=5,t=10,b=5))
        st.plotly_chart(fig, use_container_width=True, config={"scrollZoom":True})
      st.markdown("</div>", unsafe_allow_html=True)

    with col_g:
      st.markdown("<div class='panel'><div class='panel-title'>Annual Energetic Mixture (Yield)</div>", unsafe_allow_html=True)
      gen_e={}
      for c in n.generators.carrier.unique():
        if allowed_component(c):
          idx=n.generators[n.generators.carrier==c].index.intersection(n.generators_t.p.columns)
          if len(idx): gen_e[c]=n.generators_t.p[idx].multiply(wt, axis=0).sum().sum()
      if gen_e:
        df_g=pd.DataFrame(list(gen_e.items()),columns=['Carrier','Energy (MWh)'])
        fig2=px.pie(df_g,values='Energy (MWh)',names='Carrier',color_discrete_sequence=['#F59E0B','#0EA5E9','#10B981','#8B5CF6','#EF4444'], hole=0.6)
        fig2.update_traces(textposition='inside', textinfo='percent+label')
        fig2.update_layout(paper_bgcolor='rgba(0,0,0,0)',plot_bgcolor='rgba(0,0,0,0)',font_color='#1E293B',showlegend=False,margin=dict(l=5,r=5,t=10,b=5))
        st.plotly_chart(fig2, use_container_width=True, config={"scrollZoom":True})
      else:
        st.info("No active generation mixture to display.")
      st.markdown("</div>", unsafe_allow_html=True)

    # --- ROW 2: BENCHMARKS ---
    col_ely, col_st = st.columns(2)
    with col_ely:
        st.markdown("<div class='panel'><div class='panel-title'>Electrolyzer Technology Benchmark</div>", unsafe_allow_html=True)
        elx_data = []
        for c in n.links.carrier.unique():
            if 'electrolysis' in str(c).lower():
                idx = n.links[n.links.carrier==c].index
                cap = n.links.p_nom_opt[idx].sum()
                if cap > 1:
                    gen = n.links_t.p0[idx].multiply(wt, axis=0).sum().sum() if (not n.links_t.p0.empty and len(idx.intersection(n.links_t.p0.columns))) else 0
                    cf = (gen / (cap * 8760)) * 100 if cap > 0 else 0
                    elx_data.append({"Technology": str(c).replace("H2 electrolysis ", ""), "Installed Capacity (MW)": round(cap, 2), "Utilization Factor (%)": round(cf, 1)})
        if elx_data:
            df_elx = pd.DataFrame(elx_data)
            fig3 = px.bar(df_elx, x='Technology', y='Installed Capacity (MW)', text='Installed Capacity (MW)', color='Technology', color_discrete_sequence=['#8B5CF6','#10B981','#0EA5E9'])
            fig3.update_layout(paper_bgcolor='rgba(0,0,0,0)',plot_bgcolor='rgba(0,0,0,0)',font_color='#1E293B',showlegend=False,margin=dict(l=5,r=5,t=10,b=5))
            st.plotly_chart(fig3, use_container_width=True)
            st.dataframe(df_elx, use_container_width=True, hide_index=True)
        else:
            st.info("No Electrolyzer battle data to display (did they build?)")
        st.markdown("</div>", unsafe_allow_html=True)
        
    with col_st:
        st.markdown("<div class='panel'><div class='panel-title'>Storage Architecture Benchmark</div>", unsafe_allow_html=True)
        sto_data = []
        for c in n.stores.carrier.unique():
            if 'storage' in str(c).lower() or 'battery' in str(c).lower():
                idx = n.stores[n.stores.carrier==c].index
                cap = n.stores.e_nom_opt[idx].sum()
                if cap > 1:
                    capex = (n.stores.e_nom_opt[idx] * n.stores.capital_cost[idx]).sum()
                    sto_data.append({"Storage Type": str(c).replace("hydrogen ", ""), "Capacity (MWh)": round(cap, 2), "CAPEX Required (€)": f"€{capex:,.0f}"})
        if sto_data:
            df_sto = pd.DataFrame(sto_data)
            fig4 = px.pie(df_sto, names='Storage Type', values='Capacity (MWh)', color_discrete_sequence=['#10B981','#F59E0B','#0EA5E9'])
            fig4.update_layout(paper_bgcolor='rgba(0,0,0,0)',plot_bgcolor='rgba(0,0,0,0)',font_color='#1E293B',margin=dict(l=5,r=5,t=10,b=5))
            st.plotly_chart(fig4, use_container_width=True)
            st.dataframe(df_sto, use_container_width=True, hide_index=True)
        else:
            st.info("No Storage vessels constructed in model.")
        st.markdown("</div>", unsafe_allow_html=True)

    # --- ROW 3: COMPONENT PRICING MATRIX ---
    st.markdown("<div class='panel'><div class='panel-title'>Internal Component Pricing & Efficiencies</div>", unsafe_allow_html=True)
    st.markdown("<p style='color:var(--tm); font-size:1.05rem;'>These are the precise <b>solver assumptions</b> the AI Optimizer used to build this architecture based on your UI parameters.</p>", unsafe_allow_html=True)
    price_data = []
    
    # Check Generators (Solar, Wind)
    for c in n.generators.carrier.unique():
        if allowed_component(c):
            idx = n.generators[n.generators.carrier==c].index
            if len(idx):
                price_data.append({"Component": c.capitalize(), "Type": "Generator", "Base Capital Cost (€/MW)": f"€{(n.generators.capital_cost[idx].mean()):,.0f}", "Efficiency (%)": f"{(n.generators.efficiency[idx].mean()*100):.1f}%" if 'efficiency' in n.generators else "N/A"})
    
    # Check Links (Electrolyzers, Desalination, Pipelines)
    for c in n.links.carrier.unique():
        if allowed_component(c):
            idx = n.links[n.links.carrier==c].index
            if len(idx):
                if 'pipeline' in str(c).lower():
                    price_data.append({"Component": str(c).title(), "Type": "Transport Network", "Base Capital Cost (€/MW)": "€2.5 Million per km (eq. for 1000MW flow)", "Efficiency (%)": f"{(n.links.efficiency[idx].mean()*100):.1f}% / 1000km" if 'efficiency' in n.links else "N/A"})
                else:
                    price_data.append({"Component": c.title(), "Type": "Converter", "Base Capital Cost (€/MW)": f"€{(n.links.capital_cost[idx].mean()):,.0f}", "Efficiency (%)": f"{(n.links.efficiency[idx].mean()*100):.1f}%" if 'efficiency' in n.links else "N/A"})
                
    # Check Stores (Tanks, Caverns, Battery)
    for c in n.stores.carrier.unique():
        if 'storage' in str(c).lower() or 'battery' in str(c).lower():
            idx = n.stores[n.stores.carrier==c].index
            if len(idx):
                price_data.append({"Component": c.title(), "Type": "Storage", "Base Capital Cost (€/MWh)": f"€{(n.stores.capital_cost[idx].mean()):,.0f}", "Efficiency (%)": "N/A (See Chargers)"})

    if price_data:
        df_pricing = pd.DataFrame(price_data)
        st.dataframe(df_pricing, use_container_width=True, hide_index=True)
    st.markdown("</div>", unsafe_allow_html=True)
    
    # --- ROW 4: SPATIAL MAP ---
    st.markdown('<div class="glow-div"></div>', unsafe_allow_html=True)
    st.markdown("<div class='panel'><div class='panel-title'>Global Space View Routing</div>", unsafe_allow_html=True)
    fig_m=go.Figure()
    ex,ey=[],[]
    for _,row in n.lines.iterrows():
      if row.bus0 in n.buses.index and row.bus1 in n.buses.index:
        ex.extend([n.buses.at[row.bus0,'x'],n.buses.at[row.bus1,'x'],None])
        ey.extend([n.buses.at[row.bus0,'y'],n.buses.at[row.bus1,'y'],None])
    if ex: fig_m.add_trace(go.Scattermap(lat=ey,lon=ex,mode='lines',line=dict(width=1,color='rgba(0,0,0,.15)'),name='Grid Topology'))

    hx, hy = [], []
    hmx, hmy, hm_txt = [], [], []
    if not n.links.empty:
      h2_pipes = n.links[(n.links.carrier.str.contains('pipeline', case=False, na=False)) & (~n.links.carrier.str.contains('co2', case=False, na=False)) & (n.links.p_nom_opt > 1)]
      for _idx, row in h2_pipes.iterrows():
        length = row.get('length', 0)
        capex = row.capital_cost * row.p_nom_opt
        if length > 0 and capex > 0:
          if row.bus0 in n.buses.index and row.bus1 in n.buses.index:
            x0, y0 = n.buses.at[row.bus0,'x'], n.buses.at[row.bus0,'y']
            x1, y1 = n.buses.at[row.bus1,'x'], n.buses.at[row.bus1,'y']
            hx.extend([x0, x1, None])
            hy.extend([y0, y1, None])
            hmx.append((x0 + x1) / 2)
            hmy.append((y0 + y1) / 2)
            hm_txt.append(f"<b>H₂ Pipeline</b><br>Between: {row.bus0.replace(' H2','')} ↔ {row.bus1.replace(' H2','')}<br>Capacity: {row.p_nom_opt:,.0f} MW<br>Distance: {length:,.0f} km<br>CAPEX: €{capex / 1e6:,.1f} Million")
    if hx:
      fig_m.add_trace(go.Scattermap(lat=hy,lon=hx,mode='lines',line=dict(width=3,color='#00e5ff'),name=' H₂ Pipelines',hoverinfo='none'))
      fig_m.add_trace(go.Scattermap(lat=hmy,lon=hmx,mode='markers',marker=dict(size=8,color='#00e5ff',opacity=0.9),name=' H₂ Pipeline Info',text=hm_txt,hoverinfo='text'))
    
    for carrier,color,name in [('solar','#F59E0B',' Solar'),('onwind','#0EA5E9',' Wind')]:
      gl=n.generators[n.generators.carrier==carrier]
      if not gl.empty:
        cap=gl.groupby('bus').p_nom_opt.sum()
        cap=cap[cap>1]
        lats=[n.buses.at[b,'y'] for b in cap.index if b in n.buses.index]
        lons=[n.buses.at[b,'x'] for b in cap.index if b in n.buses.index]
        sz=[min(int(v/cap.max()*30)+7,40) for b,v in cap.items() if b in n.buses.index]
        txt=[f"{name}: {v:.0f} MW" for b,v in cap.items() if b in n.buses.index]
        if lats: fig_m.add_trace(go.Scattermap(lat=lats,lon=lons,mode='markers',marker=dict(size=sz,color=color,opacity=.9),name=name,text=txt,hoverinfo='text'))
    
    # Electrolyzer traces
    el=n.links[n.links.carrier.str.contains('electrolysis',case=False,na=False)]
    if not el.empty:
      cap=el.groupby('bus0').p_nom_opt.sum(); cap=cap[cap>1]
      lats=[n.buses.at[b,'y'] for b in cap.index if b in n.buses.index]
      lons=[n.buses.at[b,'x'] for b in cap.index if b in n.buses.index]
      sz=[min(int(v/cap.max()*30)+7,40) for b,v in cap.items() if b in n.buses.index]
      txt=[f" E-lyzers: {v:.0f} MW" for b,v in cap.items() if b in n.buses.index]
      if lats: fig_m.add_trace(go.Scattermap(lat=lats,lon=lons,mode='markers',marker=dict(size=sz,color='#8B5CF6',opacity=.9),name=' Electrolyzers',text=txt,hoverinfo='text'))

    # Storage traces
    st_h2=n.stores[n.stores.carrier.str.contains('storage',case=False,na=False)]
    if not st_h2.empty:
      is_cavern = st_h2.carrier.str.contains('underground', case=False, na=False) | st_h2.index.to_series().str.contains('salt cavern', case=False, na=False)
      cap = st_h2[(~is_cavern & (st_h2.e_nom_opt > 1)) | (is_cavern & (st_h2.e_nom_opt >= 100))]
      lats=[]
      lons=[]
      sz=[]
      txt=[]
      max_cap = cap.e_nom_opt.max() if not cap.empty else 0
      for idx, row in cap.iterrows():
        ac_bus = str(row.bus).replace(' H2', '')
        v = row.e_nom_opt
        if ac_bus in n.buses.index:
          lats.append(n.buses.at[ac_bus, 'y'])
          lons.append(n.buses.at[ac_bus, 'x'])
          sz.append(min(int(v/max_cap*30)+7,40) if max_cap > 0 else 10)
          
          # Clean up the node string for UI tooltips
          clean_name = str(idx).split(' H2 ')[-1] if ' H2 ' in str(idx) else str(idx)
          txt.append(f" <b>{clean_name.title()}</b><br>Capacity: {v:,.0f} MWh")
          
      if lats: fig_m.add_trace(go.Scattermap(lat=lats,lon=lons,mode='markers',marker=dict(size=sz,color='#10B981',opacity=.9),name=' Storage Components',text=txt,hoverinfo='text'))

    fig_m.update_layout(map_style="carto-positron",map=dict(center=dict(lat=34,lon=3),zoom=4.5),height=550,margin={"r":0,"t":0,"l":0,"b":0},legend=dict(yanchor="top",y=.98,xanchor="right",x=.98,bgcolor="rgba(255,255,255,0.8)",font_color="#1E293B",font_size=13))
    st.plotly_chart(fig_m, use_container_width=True, config={"scrollZoom":True})
    st.markdown("</div>", unsafe_allow_html=True)

    import numpy as np

    # --- ROW 5: NATURAL POTENTIAL (MAX INSTALLABLE CAPACITY) ---
    st.markdown('<div class="glow-div"></div>', unsafe_allow_html=True)
    st.markdown("<h4 style='font-weight: 700; color: var(--t); margin-bottom: 1rem;'>Resource Natural Potential (Installable Limit MW)</h4>", unsafe_allow_html=True)
    st.markdown("<p style='color:var(--tm); font-size:1.05rem;'>Displays the absolute theoretical maximum of MW that can physically fit within the usable land of a cluster (excluding cities, roads, mountains). Note: Solar physical density is bounded at ~1.7 MW/km² and Onshore Wind at ~3.0 MW/km².</p>", unsafe_allow_html=True)
    c_p1, c_p2 = st.columns(2)
    
    with c_p1:
        st.markdown("<div class='panel'><div class='panel-title'>Solar Natural Potential</div>", unsafe_allow_html=True)
        fig_ps = go.Figure()
        sol = n.generators[n.generators.carrier == 'solar']
        if not sol.empty and 'p_nom_max' in sol.columns:
            valid_sol = sol[(sol.p_nom_max < np.inf) & (sol.p_nom_max > 0)]
            if not valid_sol.empty:
                lats = [n.buses.at[b, 'y'] for b in valid_sol.bus if b in n.buses.index]
                lons = [n.buses.at[b, 'x'] for b in valid_sol.bus if b in n.buses.index]
                vals = valid_sol.p_nom_max.values
                # 1.7 MW per km^2
                text_hover = [f"<b>Max Potential:</b> {v:,.0f} MW<br><b>Usable Surface Required:</b> {v/1.7:,.0f} km²" for v in vals]
                fig_ps.add_trace(go.Scattermap(lat=lats, lon=lons, mode='markers',
                                              marker=dict(size=12, color=vals, colorscale='YlOrRd', showscale=True, opacity=0.9, colorbar=dict(title="MW", thickness=15, len=0.8)),
                                              text=text_hover, hoverinfo='text'))
        fig_ps.update_layout(map_style="carto-positron", map=dict(center=dict(lat=34,lon=3), zoom=3.5), height=400, margin={"r":0,"t":0,"l":0,"b":0})
        st.plotly_chart(fig_ps, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with c_p2:
        st.markdown("<div class='panel'><div class='panel-title'>Wind Natural Potential</div>", unsafe_allow_html=True)
        fig_pw = go.Figure()
        wnd = n.generators[n.generators.carrier == 'onwind']
        if not wnd.empty and 'p_nom_max' in wnd.columns:
            valid_wnd = wnd[(wnd.p_nom_max < np.inf) & (wnd.p_nom_max > 0)]
            if not valid_wnd.empty:
                lats = [n.buses.at[b, 'y'] for b in valid_wnd.bus if b in n.buses.index]
                lons = [n.buses.at[b, 'x'] for b in valid_wnd.bus if b in n.buses.index]
                vals = valid_wnd.p_nom_max.values
                # 3.0 MW per km^2
                text_hover = [f"<b>Max Potential:</b> {v:,.0f} MW<br><b>Usable Surface Required:</b> {v/3.0:,.0f} km²" for v in vals]
                fig_pw.add_trace(go.Scattermap(lat=lats, lon=lons, mode='markers',
                                              marker=dict(size=12, color=vals, colorscale='Blues', showscale=True, opacity=1.0, colorbar=dict(title="MW", thickness=15, len=0.8)),
                                              text=text_hover, hoverinfo='text'))
        fig_pw.update_layout(map_style="carto-positron", map=dict(center=dict(lat=34,lon=3), zoom=3.5), height=400, margin={"r":0,"t":0,"l":0,"b":0})
        st.plotly_chart(fig_pw, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    # --- ROW 6: CAPACITY FACTOR ---
    st.markdown('<div class="glow-div"></div>', unsafe_allow_html=True)
    st.markdown("<h4 style='font-weight: 700; color: var(--t); margin-bottom: 1rem;'>Meteorological Average Capacity Factors</h4>", unsafe_allow_html=True)
    st.markdown("<p style='color:var(--tm); font-size:1.05rem;'>Capacity Factor (CF) is the <b>statistical arithmetic mean (average)</b> of hourly weather profiles across all 8,760 hours of the year. A {20%} CF means the plant generates the equivalent of 20% of its plated maximum capacity consistently year-round.</p>", unsafe_allow_html=True)
    c_cf1, c_cf2 = st.columns(2)
    
    with c_cf1:
        st.markdown("<div class='panel'><div class='panel-title'>Solar 8760-Hour Mean CF</div>", unsafe_allow_html=True)
        fig_cfs = go.Figure()
        if not sol.empty and not n.generators_t.p_max_pu.empty:
            valid_idx = sol.index.intersection(n.generators_t.p_max_pu.columns)
            if len(valid_idx):
                cfs = n.generators_t.p_max_pu[valid_idx].mean() * 100
                lats = [n.buses.at[sol.at[i, 'bus'], 'y'] for i in valid_idx if sol.at[i, 'bus'] in n.buses.index]
                lons = [n.buses.at[sol.at[i, 'bus'], 'x'] for i in valid_idx if sol.at[i, 'bus'] in n.buses.index]
                cf_vals = cfs.values
                text_hover = [f"<b>Arithmetic Mean CF:</b> {v:.1f}%<br>(Over 8,760 hrs)" for v in cf_vals]
                fig_cfs.add_trace(go.Scattermap(lat=lats, lon=lons, mode='markers',
                                               marker=dict(size=12, color=cf_vals, colorscale='YlOrRd', showscale=True, opacity=1.0, colorbar=dict(title="CF (%)", thickness=15, len=0.8)),
                                               text=text_hover, hoverinfo='text'))
        fig_cfs.update_layout(map_style="carto-positron", map=dict(center=dict(lat=34,lon=3), zoom=3.5), height=400, margin={"r":0,"t":0,"l":0,"b":0})
        st.plotly_chart(fig_cfs, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with c_cf2:
        st.markdown("<div class='panel'><div class='panel-title'>Wind 8760-Hour Mean CF</div>", unsafe_allow_html=True)
        fig_cfw = go.Figure()
        if not wnd.empty and not n.generators_t.p_max_pu.empty:
            valid_idx = wnd.index.intersection(n.generators_t.p_max_pu.columns)
            if len(valid_idx):
                cfw = n.generators_t.p_max_pu[valid_idx].mean() * 100
                lats = [n.buses.at[wnd.at[i, 'bus'], 'y'] for i in valid_idx if wnd.at[i, 'bus'] in n.buses.index]
                lons = [n.buses.at[wnd.at[i, 'bus'], 'x'] for i in valid_idx if wnd.at[i, 'bus'] in n.buses.index]
                cf_vals = cfw.values
                text_hover = [f"<b>Arithmetic Mean CF:</b> {v:.1f}%<br>(Over 8,760 hrs)" for v in cf_vals]
                fig_cfw.add_trace(go.Scattermap(lat=lats, lon=lons, mode='markers',
                                               marker=dict(size=12, color=cf_vals, colorscale='Blues', showscale=True, opacity=1.0, colorbar=dict(title="CF (%)", thickness=15, len=0.8)),
                                               text=text_hover, hoverinfo='text'))
        fig_cfw.update_layout(map_style="carto-positron", map=dict(center=dict(lat=34,lon=3), zoom=3.5), height=400, margin={"r":0,"t":0,"l":0,"b":0})
        st.plotly_chart(fig_cfw, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 5 — LCOS COMPARISON (NG-DRI vs H2-DRI)
# ══════════════════════════════════════════════════════════════════════════════
with tab5:
  st.markdown("<h3 style='font-weight: 800;'>LCOS Comparison: NG-DRI vs H2-DRI</h3>", unsafe_allow_html=True)
  st.markdown("<p style='color:var(--tm); font-size:1.05rem;'>Levelized Cost of Steel analysis based on Bhaskar et al. LCOP methodology, auto-fed by your PyPSA simulation results.</p>", unsafe_allow_html=True)

  import numpy as np

  # --- CONSTANTS ---
  STEEL_ANNUAL_PROD = 2_200_000   # tonnes (AQS Bellara nameplate capacity)
  DISCOUNT_RATE_LCOS = 0.08
  LIFESPAN_LCOS = 25
  H2_SPECIFIC_CONS = 86.89        # kg H2 / t_steel (Rosner et al. 2022)
  NG_SPECIFIC_CONS = 2.5          # MWh NG / t_steel
  CO2_EMISSION_NG_DRI = 1.2       # t CO2 / t_steel
  CO2_EMISSION_H2_DRI = 0.05      # t CO2 / t_steel
  EAF_ELEC_NG_DRI = 0.55          # MWh / t_steel
  EAF_ELEC_H2_DRI = 0.70          # MWh / t_steel
  CBAM_SCHEDULE = dict(zip(range(2025, 2035), [0.0, 0.025, 0.05, 0.10, 0.225, 0.485, 0.61, 0.735, 0.86, 1.0]))

  def annuity_factor_lcos(r, n):
    if r == 0: return 1/n
    return (r * (1 + r)**n) / ((1 + r)**n - 1)

  # Plant economics inputs
  st.markdown("<div class='panel'><div class='panel-title'>Plant Economics & Energy Prices</div>", unsafe_allow_html=True)
  lcos_col1, lcos_col2, lcos_col3 = st.columns(3)

  with lcos_col1:
    st.markdown("**Plant Costs**")
    capex_per_ton   = st.number_input("Base Plant CAPEX (€/t capacity)", value=600.0, key="lcos_capex")
    maint_cost_pct  = st.slider("Maintenance (% of CAPEX)", 0.0, 0.05, 0.03, key="lcos_maint")
    labor_cost_t    = st.number_input("Labor & Fixed Ops (€/t)", value=65.0, key="lcos_labor")
    iron_ore_price  = st.number_input("Iron Ore Pellets (€/t)", value=130.0, key="lcos_ore")

  with lcos_col2:
    st.markdown("**Energy Prices**")
    ng_price_mwh    = st.number_input("Natural Gas Price (€/MWh)", value=35.0, key="lcos_ng")
    grid_elec_price = st.number_input("Algerian Grid Electricity (€/MWh)", value=20.68, key="lcos_elec")

  with lcos_col3:
    st.markdown("**EU CBAM Policy**")
    apply_cbam      = st.checkbox("Apply EU CBAM Tax", value=True, key="lcos_cbam")
    export_year     = st.slider("Export Year", 2025, 2034, 2030, key="lcos_year") if apply_cbam else 2025
    eu_ets_price    = st.number_input("EU ETS Carbon Price (€/t CO2)", value=75.0, key="lcos_ets") if apply_cbam else 0.0
    phase_in_factor = CBAM_SCHEDULE.get(export_year, 1.0) if apply_cbam else 0.0

  st.markdown("</div>", unsafe_allow_html=True)

  # --- Pull LCOH and LCOE from global computation (identical to Results tab) ---
  st.markdown("<div class='panel'><div class='panel-title'>PyPSA Simulation Input</div>", unsafe_allow_html=True)
  model_lcoh = _global_lcoh
  model_lcoe = _global_lcoe
  lcos_n = n  # reuse the globally loaded network

  if model_lcoh > 0 and model_lcoe > 0:
    st.success(f"Linked directly to Results Tab — LCOH = **{model_lcoh:.2f} EUR/kg** | LCOE = **{model_lcoe:.2f} EUR/MWh**")
  else:
    st.warning("No simulation results loaded yet. Using fallback values: LCOH = 3.5 EUR/kg, LCOE = 30 EUR/MWh.")
    model_lcoh = model_lcoh or 3.5
    model_lcoe = model_lcoe or 30.0
  st.markdown("</div>", unsafe_allow_html=True)

  # --- LCOP Core Calculation ---
  ACC = annuity_factor_lcos(DISCOUNT_RATE_LCOS, LIFESPAN_LCOS)

  def calculate_lcop(is_h2_case, h2_price=0.0):
    base_capex = capex_per_ton * STEEL_ANNUAL_PROD
    capex_annuity_per_t = (base_capex * ACC) / STEEL_ANNUAL_PROD
    maint_per_t = capex_per_ton * maint_cost_pct
    ore_cost = iron_ore_price * 1.45
    if is_h2_case:
      elec_cost = EAF_ELEC_H2_DRI * grid_elec_price
      reductant_cost = H2_SPECIFIC_CONS * h2_price
      emissions = CO2_EMISSION_H2_DRI
      capex_annuity_per_t *= 1.10  # H2-shaft modification premium
    else:
      elec_cost = EAF_ELEC_NG_DRI * grid_elec_price
      reductant_cost = NG_SPECIFIC_CONS * ng_price_mwh
      emissions = CO2_EMISSION_NG_DRI
    cbam_tax = emissions * phase_in_factor * eu_ets_price if apply_cbam else 0.0
    return capex_annuity_per_t + maint_per_t + labor_cost_t + ore_cost + elec_cost + reductant_cost + cbam_tax

  lcos_ng  = calculate_lcop(is_h2_case=False)
  lcos_h2  = calculate_lcop(is_h2_case=True, h2_price=model_lcoh)
  delta_vs_ng = lcos_h2 - lcos_ng
  cbam_ng_cost = CO2_EMISSION_NG_DRI * phase_in_factor * eu_ets_price if apply_cbam else 0.0

  # --- KEY METRICS ROW ---
  st.markdown('<div class="glow-div"></div>', unsafe_allow_html=True)
  m1, m2, m3, m4 = st.columns(4)
  m1.markdown(f'<div class="mcard" style="box-shadow:inset 0 0 20px rgba(0,229,255,0.1);"><div class="lbl">PyPSA Green H₂ Price</div><div class="val">{model_lcoh:.2f}</div><div class="unit">€ / kg H₂</div></div>', unsafe_allow_html=True)
  m2.markdown(f'<div class="mcard" style="box-shadow:inset 0 0 20px rgba(239,85,59,0.15);"><div class="lbl">NG-DRI Benchmark ({export_year})</div><div class="val">{lcos_ng:,.0f}</div><div class="unit">€ / Tonne Steel</div></div>', unsafe_allow_html=True)
  color_delta = "rgba(0,204,150,0.15)" if delta_vs_ng < 0 else "rgba(255,85,85,0.15)"
  m3.markdown(f'<div class="mcard" style="box-shadow:inset 0 0 20px {color_delta};"><div class="lbl">H₂-DRI (PyPSA-DZ)</div><div class="val">{lcos_h2:,.0f}</div><div class="unit">€ / Tonne Steel</div></div>', unsafe_allow_html=True)
  sign = "+" if delta_vs_ng >= 0 else ""
  m4.markdown(f'<div class="mcard" style="box-shadow:inset 0 0 20px rgba(157,78,221,0.1);"><div class="lbl">CBAM Penalty on NG-DRI</div><div class="val">{cbam_ng_cost:.0f}</div><div class="unit">€ / Tonne (Carbon Tax)</div></div>', unsafe_allow_html=True)

  st.markdown('<div class="glow-div"></div>', unsafe_allow_html=True)

  # --- CHARTS ---
  chart_col1, chart_col2 = st.columns(2)

  with chart_col1:
    st.markdown("<div class='panel'><div class='panel-title'>📊 Competitiveness Bar Comparison</div>", unsafe_allow_html=True)
    comp_df = pd.DataFrame({
      "Route": ["NG-DRI (Benchmark)", "H2-DRI (PyPSA-DZ)"],
      "LCOS (€/t)": [lcos_ng, lcos_h2]
    })
    fig_bar = px.bar(comp_df, x="Route", y="LCOS (€/t)", color="Route", text_auto='.1f',
                     color_discrete_map={"NG-DRI (Benchmark)": "#EF553B", "H2-DRI (PyPSA-DZ)": "#00CC96"},
                     title=f"LCOS Comparison ({export_year})")
    fig_bar.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                          font_color='#1E293B', showlegend=False,
                          title_font_size=14, margin=dict(l=10, r=10, t=40, b=10))
    fig_bar.update_traces(textposition='outside')
    st.plotly_chart(fig_bar, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

  with chart_col2:
    st.markdown("<div class='panel'><div class='panel-title'>📈 Break-Even Sensitivity: H₂ Cost vs LCOS</div>", unsafe_allow_html=True)
    h2_range = np.linspace(0.5, 8.0, 60)
    lcos_range = [calculate_lcop(is_h2_case=True, h2_price=h) for h in h2_range]

    fig_sens = px.line(x=h2_range, y=lcos_range,
                       labels={'x': 'Green H₂ Cost (€/kg)', 'y': 'H₂-DRI LCOS (€/t)'},
                       title="Break-Even H₂ Price Analysis")
    fig_sens.add_hline(y=lcos_ng, line_dash='dash', line_color='#EF553B',
                       annotation_text=f"NG-DRI Benchmark ({lcos_ng:.0f} €/t)", annotation_position="top right")
    fig_sens.add_vline(x=model_lcoh, line_dash='dash', line_color='#00CC96',
                       annotation_text=f"PyPSA H₂: {model_lcoh:.2f} €/kg", annotation_position="top left")

    # Compute break-even numerically
    fixed_h2_costs = calculate_lcop(is_h2_case=True, h2_price=0.0)
    breakeven_h2 = (lcos_ng - fixed_h2_costs) / H2_SPECIFIC_CONS
    if 0 < breakeven_h2 < 8:
      fig_sens.add_vline(x=breakeven_h2, line_dash='dot', line_color='#0EA5E9',
                         annotation_text=f"Break-even: {breakeven_h2:.2f} €/kg", annotation_position="bottom right")

    fig_sens.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0.02)',
                           font_color='#1E293B', title_font_size=14,
                           margin=dict(l=10, r=10, t=40, b=10))
    st.plotly_chart(fig_sens, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

  # --- COST STACK BREAKDOWN ---
  st.markdown('<div class="glow-div"></div>', unsafe_allow_html=True)
  st.markdown("<div class='panel'><div class='panel-title'>🧱 Full Cost Stack Breakdown (€/tonne steel)</div>", unsafe_allow_html=True)
  ACC_val = annuity_factor_lcos(DISCOUNT_RATE_LCOS, LIFESPAN_LCOS)
  stack_ng = {
    "Plant CAPEX (Annuity)": capex_per_ton * ACC_val,
    "Maintenance": capex_per_ton * maint_cost_pct,
    "Labor & Fixed": labor_cost_t,
    "Iron Ore": iron_ore_price * 1.45,
    "Grid Electricity (EAF)": EAF_ELEC_NG_DRI * grid_elec_price,
    "Natural Gas (Reductant)": NG_SPECIFIC_CONS * ng_price_mwh,
    "CBAM Carbon Tax": CO2_EMISSION_NG_DRI * phase_in_factor * eu_ets_price if apply_cbam else 0.0,
  }
  stack_h2 = {
    "Plant CAPEX (Annuity)": capex_per_ton * ACC_val * 1.10,
    "Maintenance": capex_per_ton * maint_cost_pct,
    "Labor & Fixed": labor_cost_t,
    "Iron Ore": iron_ore_price * 1.45,
    "Grid Electricity (EAF)": EAF_ELEC_H2_DRI * grid_elec_price,
    "Green Hydrogen": H2_SPECIFIC_CONS * model_lcoh,
    "CBAM Carbon Tax": CO2_EMISSION_H2_DRI * phase_in_factor * eu_ets_price if apply_cbam else 0.0,
  }
  stack_df = pd.DataFrame({
    "Cost Component": list(stack_ng.keys()),
    "NG-DRI (€/t)": list(stack_ng.values()),
    "H2-DRI (€/t)": [stack_h2.get(k, 0) for k in stack_ng.keys()]
  })
  fig_stack = px.bar(stack_df.melt(id_vars="Cost Component", var_name="Route", value_name="€/t"),
                     x="Cost Component", y="€/t", color="Route", barmode="group",
                     color_discrete_map={"NG-DRI (€/t)": "#EF553B", "H2-DRI (€/t)": "#00CC96"},
                     title="Cost Stack Breakdown per Tonne of Steel")
  fig_stack.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0.02)',
                          font_color='#1E293B', title_font_size=14,
                          xaxis_tickangle=-30, margin=dict(l=10, r=10, t=40, b=80))
  st.plotly_chart(fig_stack, use_container_width=True)
  st.dataframe(stack_df.style.format({"NG-DRI (€/t)": "{:.1f}", "H2-DRI (€/t)": "{:.1f}"}),
               use_container_width=True, hide_index=True)
  st.markdown("</div>", unsafe_allow_html=True)

  st.markdown("</div>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 6 — INVESTMENT ANALYSIS (H2-DRI Green Route)
# ══════════════════════════════════════════════════════════════════════════════
with tab6:
  st.markdown("<h3 style='font-weight: 800;'>Green Steel Project Investment Analysis</h3>", unsafe_allow_html=True)
  st.markdown("<p style='color:var(--tm);font-size:1.05rem;'>Total capital required, annual cash flows, payback period, and ROI for the H2-DRI green steel route.</p>", unsafe_allow_html=True)
  st.markdown('<div class="glow-div"></div>', unsafe_allow_html=True)
  st.markdown("<div class='panel'><div class='panel-title'>Project Investment & Financial Return Analysis</div>", unsafe_allow_html=True)

  inv_col1, inv_col2, inv_col3 = st.columns(3)
  with inv_col1:
    st.markdown("**Revenue Assumptions**")
    steel_price_market = st.number_input("Market Price of Green Steel (\u20ac/t)", value=800.0, key="inv_steel_price")
    utilization_rate   = st.slider("Plant Utilization Rate (%)", 50, 100, 90, key="inv_util") / 100.0
  with inv_col2:
    st.markdown("**PyPSA Infrastructure CAPEX**")
    if lcos_n is not None:
      try:
        _pypsa_capex_total = (
          (lcos_n.generators.capital_cost * lcos_n.generators.p_nom_opt).sum() / annuity_factor_lcos(DISCOUNT_RATE_LCOS, LIFESPAN_LCOS) +
          (lcos_n.links.capital_cost      * lcos_n.links.p_nom_opt).sum()      / annuity_factor_lcos(DISCOUNT_RATE_LCOS, LIFESPAN_LCOS) +
          (lcos_n.stores.capital_cost     * lcos_n.stores.e_nom_opt).sum()     / annuity_factor_lcos(DISCOUNT_RATE_LCOS, LIFESPAN_LCOS)
        )
        pypsa_infra_capex_m = _pypsa_capex_total / 1e6
      except Exception:
        pypsa_infra_capex_m = 500.0
    else:
      pypsa_infra_capex_m = 500.0
    st.metric("Solar + Wind + H\u2082 Infra", f"\u20ac{pypsa_infra_capex_m:,.0f}M", help="Overnight CAPEX from PyPSA solver")
  with inv_col3:
    st.markdown("**DRI-EAF Plant CAPEX**")
    plant_capex_total_m = (capex_per_ton * STEEL_ANNUAL_PROD) / 1e6
    st.metric("DRI Shaft + EAF Furnace", f"\u20ac{plant_capex_total_m:,.0f}M", help="Nameplate capacity overnight CAPEX")

  # ── FINANCIAL COMPUTATIONS ────────────────────────────────────────────────────
  effective_prod   = STEEL_ANNUAL_PROD * utilization_rate
  total_capex_h2   = pypsa_infra_capex_m * 1e6 + plant_capex_total_m * 1.10 * 1e6
  total_capex_ng   = plant_capex_total_m * 1e6
  annual_revenue   = effective_prod * steel_price_market
  annual_opex_h2   = lcos_h2 * effective_prod
  annual_opex_ng   = lcos_ng * effective_prod
  annual_profit_h2 = annual_revenue - annual_opex_h2
  annual_profit_ng = annual_revenue - annual_opex_ng
  payback_h2 = total_capex_h2 / annual_profit_h2 if annual_profit_h2 > 0 else float('inf')
  payback_ng = total_capex_ng / annual_profit_ng if annual_profit_ng > 0 else float('inf')

  def _npv(cashflow, capex, r, n):
    return sum(cashflow / (1 + r)**t for t in range(1, n+1)) - capex

  npv_h2 = _npv(annual_profit_h2, total_capex_h2, DISCOUNT_RATE_LCOS, LIFESPAN_LCOS)
  npv_ng = _npv(annual_profit_ng, total_capex_ng, DISCOUNT_RATE_LCOS, LIFESPAN_LCOS)
  roi_h2 = ((annual_profit_h2 * LIFESPAN_LCOS - total_capex_h2) / total_capex_h2 * 100) if total_capex_h2 > 0 else 0
  roi_ng = ((annual_profit_ng * LIFESPAN_LCOS - total_capex_ng) / total_capex_ng * 100) if total_capex_ng > 0 else 0

  # H2-DRI five metric cards
  st.markdown('<div class="glow-div"></div>', unsafe_allow_html=True)
  st.markdown("**H2-DRI Green Route (PyPSA-DZ)**")
  a1, a2, a3, a4, a5 = st.columns(5)
  a1.markdown(f'<div class="mcard" style="box-shadow:inset 0 0 20px rgba(0,229,255,0.15);"><div class="lbl">Total Investment Required</div><div class="val">\u20ac{total_capex_h2/1e9:,.2f}B</div><div class="unit">Overnight CAPEX (Infra + Plant)</div></div>', unsafe_allow_html=True)
  a2.markdown(f'<div class="mcard" style="box-shadow:inset 0 0 20px rgba(0,204,150,0.15);"><div class="lbl">Annual Net Profit</div><div class="val">\u20ac{annual_profit_h2/1e6:,.0f}M</div><div class="unit">Revenue \u2212 Full OPEX / yr</div></div>', unsafe_allow_html=True)
  pb_col_h2 = "rgba(0,204,150,0.15)" if payback_h2 < 15 else "rgba(255,170,0,0.15)"
  a3.markdown(f'<div class="mcard" style="box-shadow:inset 0 0 20px {pb_col_h2};"><div class="lbl">Simple Payback Period</div><div class="val">{"&#8734;" if payback_h2 == float("inf") else f"{payback_h2:.1f} yrs"}</div><div class="unit">Break-even horizon</div></div>', unsafe_allow_html=True)
  nc_col = "rgba(0,204,150,0.15)" if npv_h2 > 0 else "rgba(255,85,85,0.15)"
  a4.markdown(f'<div class="mcard" style="box-shadow:inset 0 0 20px {nc_col};"><div class="lbl">NPV ({DISCOUNT_RATE_LCOS*100:.0f}%, {LIFESPAN_LCOS}yr)</div><div class="val">\u20ac{npv_h2/1e9:,.2f}B</div><div class="unit">Net Present Value</div></div>', unsafe_allow_html=True)
  rc_col = "rgba(0,204,150,0.15)" if roi_h2 > 0 else "rgba(255,85,85,0.15)"
  a5.markdown(f'<div class="mcard" style="box-shadow:inset 0 0 20px {rc_col};"><div class="lbl">Lifetime ROI</div><div class="val">{roi_h2:+,.0f}%</div><div class="unit">Over {LIFESPAN_LCOS}-year project</div></div>', unsafe_allow_html=True)

  # Cumulative cashflow chart (H2 only)
  st.markdown('<div class="glow-div"></div>', unsafe_allow_html=True)
  st.markdown(f"<div class='panel'><div class='panel-title'>Cumulative Net Cashflow Timeline (Year 0 to {LIFESPAN_LCOS})</div>", unsafe_allow_html=True)

  years  = list(range(0, LIFESPAN_LCOS + 1))
  cf_h2  = [-total_capex_h2] + [annual_profit_h2] * LIFESPAN_LCOS
  cum_h2 = [sum(cf_h2[:i+1]) for i in range(len(cf_h2))]

  fig_cf = go.Figure()
  fig_cf.add_trace(go.Scatter(
    x=years, y=[v/1e9 for v in cum_h2], name='H\u2082-DRI (Green)',
    line=dict(color='#00CC96', width=3), fill='tozeroy', fillcolor='rgba(0,204,150,0.10)'
  ))
  fig_cf.add_hline(y=0, line_color='#64748B', line_dash='dot', line_width=1.5,
                   annotation_text='Break-even', annotation_position='bottom right')
  if payback_h2 != float('inf') and payback_h2 <= LIFESPAN_LCOS:
    fig_cf.add_vline(x=payback_h2, line_dash='dot', line_color='#00CC96',
                     annotation_text=f'Payback: {payback_h2:.1f}yr', annotation_position='top left')
  fig_cf.update_layout(
    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0.02)', font_color='#1E293B',
    xaxis_title='Year', yaxis_title='Cumulative Cashflow (Billion \u20ac)',
    margin=dict(l=10, r=10, t=50, b=10), height=380
  )
  st.plotly_chart(fig_cf, use_container_width=True)
  st.markdown("</div>", unsafe_allow_html=True)
  st.markdown("</div>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 7 — DOCUMENTATION
# ══════════════════════════════════════════════════════════════════════════════
with tab7:
  st.markdown("<h3 style='font-weight: 800;'>Mathematical Model & Architecture Documentation</h3>", unsafe_allow_html=True)
  doc_path = os.path.join(WORK_DIR, "pypsa_the_complete_academic_guide.md")
  if os.path.exists(doc_path):
    with open(doc_path, "r", encoding="utf-8") as f:
      st.markdown(f.read())
  else:
    st.warning(f"Documentation file not found at: {doc_path}")

# Footer
st.markdown(f"<p style='text-align:center;color:rgba(255,255,255,.3);font-size:.85rem;margin-top:2rem;font-weight:600;'>PyPSA-DZ Advanced Control Center Analytics Array &bull; {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>", unsafe_allow_html=True)
