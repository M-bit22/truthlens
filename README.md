# TruthLens (Streamlit version)

Same model, word explanations and fact-check lookup as the Docker version, as one Streamlit app.

## Before you deploy
1. Copy `model.joblib` and `metrics.json` from your trained project's `models` folder into `models/`.
2. In the virtual environment you trained in, run `python tools/pin_versions.py`. It writes `requirements.txt`
   with the exact scikit-learn version your model was saved with (a saved model must be loaded by the same version).
3. Test locally: `pip install streamlit`, then `streamlit run streamlit_app.py`.

## Deploy on Streamlit Community Cloud
1. Push this folder to a GitHub repository (make sure `models/model.joblib` is included).
2. share.streamlit.io -> Create app -> pick the repo, branch `main`, main file `streamlit_app.py`.
3. Advanced settings: choose the same Python version as your local one, and paste your secret:
   `GOOGLE_FACTCHECK_API_KEY = "your-key"`
4. Deploy.

Never commit your key. `.env` and `.streamlit/secrets.toml` are git-ignored.
