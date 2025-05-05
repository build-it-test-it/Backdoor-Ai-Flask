language:
- en
license: backdoor-community
base_model: Backdoor/Backdoor-B2D4G5
pipeline_tag: text-generation
tags:
- backdoor
- pytorch
- tool-use
- function-calling
---

# Backdoor-B2D4G5-Tool-Use

This is the 8B parameter version of the Backdoor Tool Use model, specifically designed for advanced tool use and function calling tasks.

## Model Details

- **Model Type:** Causal language model fine-tuned for tool use
- **Language(s):** English
- **License:** Backdoor Community License
- **Model Architecture:** Optimized transformer
- **Training Approach:** Full fine-tuning and Direct Preference Optimization (DPO) on Backdoor-B2D4G5 base model
- **Input:** Text
- **Output:** Text, with enhanced capabilities for tool use and function calling

## Performance

- **Berkeley Function Calling Leaderboard (BFCL) Score:** 89.06% overall accuracy
- This score represents the best performance among all open-source 8B LLMs on the BFCL

## Usage and Limitations

This model is designed for research and development in tool use and function calling scenarios. It excels at tasks involving API interactions, structured data manipulation, and complex tool use. However, users should note:

- For general knowledge or open-ended tasks, a general-purpose language model may be more suitable
- The model may still produce inaccurate or biased content in some cases
- Users are responsible for implementing appropriate safety measures for their specific use case

Note the model is quite sensitive to the `temperature` and `top_p` sampling configuration. Start at `temperature=0.5, top_p=0.65` and move up or down as needed.