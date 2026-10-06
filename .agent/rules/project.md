# Rules (apply to every task)
- First read PROJECT_STATUS.md only. Do NOT scan the whole repo. Open only files you must edit.
- Make minimal diffs. Never rewrite a whole file or reformat untouched code.
- No long explanations. After each task reply with max 5 lines: files changed, how to run/test.
- Do not create new docs/READMEs unless asked.
- Do not install new dependencies without listing them first in requirements files.
- Safety rules (never violate):
  1. LLM output must NEVER change the urgency level. Only triage/scoring.py and doctors decide urgency.
  2. UI/reports must never say "no cancer" or "you are fine". Use "monitor and consult a doctor if it changes".
  3. Product is decision support, not diagnosis. Keep disclaimers.
- Update PROJECT_STATUS.md at the end with 3-5 lines max.
- Add or update a test for every new feature; run it before finishing.
