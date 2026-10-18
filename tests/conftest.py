import os

# Tests must never shell out to a real LLM.
os.environ["REACHAI_LLM_BACKEND"] = "none"
