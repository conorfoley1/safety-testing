# safety-testing
Repository for files and scripts in CNS safety testing workflow

1. Question + answer selection
https://community.macmillan.org.uk/cancer_experiences/ask_the_expert-forum/ask_a_nurse
Manually write URLs to csv
File: input_urls.csv

3. Automated extraction of question/answer pairs
Extraction script
File: macmillan_ask_a_nurse_scrape.py

5. Cleaning answers
Combination of automated and manual cleaning. Lots of very frustrating issues with character rendering. Obviously this should be automated but it was quicker to do manually. 

6. Generation of LLM responses
Via OpenAI API

7. Building webapp
Hosted on hugging face at
https://huggingface.co/spaces/conor-foley/cns_safety_testing

Code in folder: 
https://huggingface.co/spaces/conor-foley/cns_safety_testing/tree/main

9. Documenting Responses
Available at https://huggingface.co/datasets/conor-foley/ab-testing-logs/tree/main

10. Analysis
tbd
